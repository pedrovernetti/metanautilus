#!/usr/bin/python

# =============================================================================================
#
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# This script must/should come together with a copy of the GNU General Public License. If not,
# access <http://www.gnu.org/licenses/> to find and read it.
#
# Author: Pedro Vernetti G.
# Name: Metanautilus
# Description: Nautilus extension which adds support to multiple details/metadata from files.
#
# #  In order to have this script working (if it is currently not), run 'install.sh'. In case
#    it is missing or does not work, follow these steps:
# 1. install pip (Python package installer) and python-nautilus (Python   .
#    binding for Nautilus components) using your package manager;         .
# 2. with pip, install lxml, pymediainfo, mutagen, mido, pillow, pyexiv2, .
#    pypdf2, olefile and torrentool;                                      .
# 3. place at '/usr/share/metanautilus/' all the *.map files accompanying .
#    this script (such as suffixToMethod.map);                            .
# 4. place this script at the nautilus-python extensions folder (which    .
#    uses to be '/usr/share/nautilus-python/extensions');                 .
# 5. restart Nautilus (run 'nautilus -q; nautilus').                      .
#
# =============================================================================================

# Basic stuff
import sys, os
pythonIs2OrOlder = (sys.version_info.major <= 2)
from threading import Thread, activeCount, Lock
from datetime import datetime
from time import sleep
try: from urllib import unquote
except: from urllib import parse as unquote
from pickle import dump as dumpPickle, load as loadPickle, PickleError
try: from queue import Queue as queue
except: from queue import queue as queue

# Nautilus/GI/... stuff
from gi import require_version
require_version("Gtk", "3.0")
require_version('Nautilus', '3.0')
from gi.repository import GLib, Nautilus, GObject, Gtk
GLib.threads_init()
GObject.threads_init()

# Tool to handle XML-based formats
from lxml import html, etree, objectify

# Tool to handle ZIP-compressed formats
from zipfile import ZipFile as ZIPFile

# Tools to fetch metadata from documents
import re
from PyPDF2 import PdfFileReader as PDFFile
from PyPDF2.generic import IndirectObject as PDFIndirectObject
try: from olefile import OleFileIO as OLEFile
except: from OleFileIO_PL import OleFileIO as OLEFile

# Tools to fetch metadata from audio/video
from pymediainfo import MediaInfo
import mutagen.id3, mutagen.apev2, mutagen.aac, mutagen.flac, mutagen.mp4, mutagen.optimfrog, mutagen.smf

import mutagen.dsf, mutagen.trueaudio

# Tools to fetch metadata from images
from PIL import Image
import pyexiv2

# Tools to fetch metadata from other kinds of files
from torrentool.api import Torrent

# =============================================================================================

placeholder = u"\u2014" # "Em Dash"
maxFieldSize = 100
minFilesToCache = 20
ignoreNonLocalFiles = False
maximumNonLocalFileSize = 268435456 # 256MB
prefetchSubfolders = True

# =============================================================================================

class fileMetadata():

    def __init__( self ):
        self.album = placeholder
        self.artist = placeholder
        self.author = placeholder
        self.bitrate = placeholder
        self.camera = placeholder
        self.comment = placeholder
        self.company = placeholder
        self.date = placeholder
        self.duration = placeholder
        self.genre = placeholder
        self.height = placeholder
        self.pages = placeholder
        self.samplerate = placeholder
        self.title = placeholder
        self.tracknumber = placeholder
        self.width = placeholder
        self.exif_flash = placeholder

    def nonBlankFields( self ):
        nonBlankCount = 0
        if (self.album != placeholder): nonBlankCount += 1
        if (self.artist != placeholder): nonBlankCount += 1
        if (self.author != placeholder): nonBlankCount += 1
        if (self.bitrate != placeholder): nonBlankCount += 1
        if (self.camera != placeholder): nonBlankCount += 1
        if (self.comment != placeholder): nonBlankCount += 1
        if (self.company != placeholder): nonBlankCount += 1
        if (self.date != placeholder): nonBlankCount += 1
        if (self.duration != placeholder): nonBlankCount += 1
        if (self.genre != placeholder): nonBlankCount += 1
        if (self.height != placeholder): nonBlankCount += 1
        if (self.pages != placeholder): nonBlankCount += 1
        if (self.samplerate != placeholder): nonBlankCount += 1
        if (self.title != placeholder): nonBlankCount += 1
        if (self.tracknumber != placeholder): nonBlankCount += 1
        if (self.width != placeholder): nonBlankCount += 1
        if (self.exif_flash != placeholder): nonBlankCount += 1
        return nonBlankCount

# =============================================================================================

class Metanautilus( GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider ):

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # INPUT/OUTPUT
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _unmute( self ):
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__

    def _mute( self ):
        try: sys.stderr = sys.stdout = open(os.devnull, 'w')
        except: self._unmute()

    def logMessage( self, message, isWarning = False ):
        now = datetime.now()
        prettyTime = ("{:%H:%M:%S.}".format(now) + str(now.microsecond * 1000))[:12]
        if (isWarning):
            if (self._lastWarning == message): return
            self._lastWarning = message
            sys.__stderr__.write("Metanautilus-\x1B[33;1mWARNING\x1B[0;0m: ")
            sys.__stderr__.write("\x1B[34m" + prettyTime + "\x1B[0m: " + message + "\n")
        else:
            sys.__stdout__.write("Metanautilus: ")
            sys.__stdout__.write("\x1B[34m" + prettyTime + "\x1B[0m: " + message + "\n")
        
    def _logException( self, exception, relatedFilePath = None ):
        traceback = sys.exc_info()[2]
        errorText = self._unicode(exception, 'ascii', True)
        errorFile = os.path.split(traceback.tb_frame.f_code.co_filename)[1]
        errorLine = str(traceback.tb_lineno)
        details = ": \x1B[3m" + errorText + "\x1B[0m at " + errorFile + ", line " + errorLine
        if (relatedFilePath is not None): details = " from '" + relatedFilePath + "'" + details
        self.logMessage(("Error fetching metadata" + details), True)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # MANAGING AND USING THE CACHES
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def pickleKnownMetadata( self ):
        self.logMessage("Pickling currently known metadata...")
        self._knownMetadataMutex.acquire()
        if ((not os.path.exists(self._cacheFile)) or os.path.isfile(self._cacheFile)):
            with open(self._cacheFile, 'wb') as cacheHandle:
                try: dumpPickle(self._knownFiles, cacheHandle, protocol=2)
                except PickleError: self.logMessage("Failed to pickle known metadata...", True)
        self._unpickledKnownFiles = 0
        self._knownMetadataMutex.release()

    def pickleKnownJunk( self ):
        self.logMessage("Pickling list of currently known junk...")
        self._knownJunkMutex.acquire()
        if ((not os.path.exists(self._junkCacheFile)) or os.path.isfile(self._junkCacheFile)):
            with open(self._junkCacheFile, 'wb') as cacheHandle:
                try: dumpPickle(self._knownJunk, cacheHandle, protocol=2)
                except PickleError: self.logMessage("Failed to pickle known junk list...", True)
        self._unpickledKnownFiles = 0
        self._knownJunkMutex.release()

    def _keepKnownInformationPickled( self ):
        cycle = 0
        while True:
            sleep(3)
            if (self._unpickledKnownFiles > 0):
                if (not os.path.exists(self._cacheFile)):
                    self.logMessage("Forgetting all metadata (pickle file removed)...")
                    self._knownMetadataMutex.acquire()
                    self._knownFiles = dict()
                    self._unpickledKnownFiles = 0
                    self._knownMetadataMutex.release()
                    with open(self._cacheFile, 'a'): pass
                elif (self._unpickledKnownFiles > minFilesToCache) or ((cycle % 10) == 0):
                    self.pickleKnownMetadata()
            if (self._unpickledKnownJunk > 0):
                if (not os.path.exists(self._junkCacheFile)):
                    self.logMessage("Forgetting all known junk (pickle file removed)...")
                    self._knownJunkMutex.acquire()
                    self._knownJunk = dict()
                    self._unpickledKnownJunk = 0
                    self._knownJunkMutex.release()
                    with open(self._junkCacheFile, 'a'): pass
                elif (self._unpickledKnownJunk > minFilesToCache) or ((cycle % 10) == 0):
                    self.pickleKnownJunk()
            if (cycle == 1000): cycle = 1
            else: cycle += 1
            sleep(12)

    def _remember( self, metadata, fileStatus ):
        if (metadata.nonBlankFields() == 0):
            self._knownJunkMutex.acquire()
            self._knownJunk[fileStatus.st_ino] = fileStatus.st_mtime
            self._unpickledKnownFiles += 1
            self._knownJunkMutex.release()
        else:
            self._knownMetadataMutex.acquire()
            self._knownFiles[fileStatus.st_ino] = (fileStatus.st_mtime, metadata)
            self._unpickledKnownJunk += 1
            self._knownMetadataMutex.release()

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # PERFORMING SOME SUBTASKS
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _cleanASCII( self, someString ):
        return (re.sub(r'[\x00-\x1F\x7F-\xFF]', '', someString))
    
    def _unicode( self, something, encoding = 'utf_8', ignoreErrors = False ):
        if (something is None): return u''
        result = u''
        errorsMode = ('ignore' if (ignoreErrors) else 'replace')
        try:
            if (pythonIs2OrOlder): 
                if (isinstance(something, unicode)): return something
                try: result = unicode(something, encoding)
                except UnicodeError: result = unicode(something, 'ascii', errorsMode)
            else:
                if (isinstance(something, str)): return something
                try: result = str(something, encoding)
                except UnicodeError: result = str(something, 'ascii', errorsMode)
        except LookupError:
            result = self._unicode(something, 'ascii', ignoreErrors)
        except TypeError:
            try: result = str(something)
            except: pass
        except:
            pass
        return result
    
    def _parsedDuration( self, durationString ):
        durationParts = durationString.split(':')
        return ((int(durationParts[0]) * 2400) + (int(durationParts[1]) * 60) + int(durationParts[2]))
    
    def _parsedXML( self, file ):
        try: parsedXML = etree.parse(file, etree.XMLParser(remove_blank_text=True, remove_comments=True))
        except: return None
        for element in parsedXML.getroot().getiterator():
            if (not hasattr(element.tag, 'find')): continue
            position = element.tag.find('}')
            if (position >= 0): element.tag = element.tag[(position + 1):]      
        return parsedXML

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FORMATTING METADATA
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _reformatedDate( self, dateString ):
        if (re.compile(r'^[0-9][0-9]?/[0-9][0-9]?/[0-9]{4}.*$').match(dateString)):
            dateString = dateString.split('/')
            if (int(dateString[1]) > 12):
                month = '%02i' % int(dateString[0])
                day = '%02i' % int(dateString[1])
            else:
                month = '%02i' % int(dateString[1])
                day = '%02i' % int(dateString[0])
            return (dateString[2][:4] + '-' + month + '-' + day)
        else:
            return placeholder

    def _formatedDate( self, dateString ):
        if (dateString is None): return placeholder
        dateString = self._unicode(dateString, 'ascii', True)
        finalString = ''
        for c in dateString:
            if ((c <= '9') and (c >= '0')): finalString += c
            elif (c == '/'): return self._reformatedDate(dateString)
        size = len(finalString)
        if (size >= 8): return (finalString[:4] + '-' + finalString[4:][:2] + '-' + finalString[6:][:2])
        elif (size >= 6): return (finalString[:4] + '-' + finalString[4:][:2] + '-??')
        elif (size >= 4): return (finalString[:4] + '-??-??')
        else: return placeholder

    def _formatedDuration( self, secs ):
        return '%02i:%02i:%02i' % (int(secs // 3600), int((secs // 60) % 60), int(secs % 60))
        
    def _formatedHTMLPiece( self, htmlString, encoding = 'utf_8' ):
        if (htmlString is None): return placeholder
        finalString = self._unicode(htmlString, encoding)
        finalString = html.document_fromstring(finalString).text_content().replace('\n', ' ')
        if (len(finalString) < 1): return placeholder
        finalString = finalString.strip()
        if (len(finalString) <= maxFieldSize): return finalString
        else: return (finalString[:(maxFieldSize - 3)] + ' [...]')

    def _formatedNumber( self, numberString ):
        finalString = ''
        for c in numberString:
            if (c <= '9') and (c >= '0'): finalString += c
        return finalString

    def _formatedString( self, anyString, encoding = 'utf_8' ):
        if (anyString is None): return placeholder
        anyString = self._unicode(anyString, encoding)
        if (len(anyString) < 1): return placeholder
        anyString = anyString.replace('\x00', '').replace('\n', ' ').replace('\r', ' ').strip()
        if (len(anyString) < 1): return placeholder
        elif (len(anyString) > maxFieldSize): anyString = anyString[:(maxFieldSize - 3)] + ' [...]'
        return anyString

    def _formatedStringList( self, stringList, encoding = 'utf_8' ):
        if (not isinstance(stringList, list)): stringList = [stringList]
        if (len(stringList) == 1): return self._formatedString(stringList[0])
        elif (len(stringList) == 0): return placeholder
        finalString = u''
        for item in stringList: 
            if (item is None): continue
            item = self._unicode(item).replace('\n', ' ').replace('\r', ' ').strip()
            if (len(item) <= 1): continue
            if ((len(finalString) + len(item)) > maxFieldSize): 
                if (len(finalString) > 2): finalString += u'...'
                else: finalString = self._formatedString(item)
                break
            finalString += item + u'; '
        finalString = finalString.replace('\x00', '')[:-1]
        if (len(finalString) < 2): return placeholder
        elif (len(finalString) <= maxFieldSize): return finalString
        else: return (finalString[:(maxFieldSize - 3)] + ' [...]')

    def _formatedTrackNumber( self, trackNumberString ):
        pos = 0
        for c in trackNumberString:
            if (c > '9') or (c < '0'): break
            pos += 1
        if (pos == 0): return placeholder
        elif (pos == 1): return '0' + trackNumberString[0]
        return trackNumberString[:pos]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FETCHING METADATA FROM DOCUMENTS
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _fetchEPUBMetadata( self, metadata, path ):
        try: XMLMetadataFile = ZIPFile(path, 'r').open('content.opf')
        except: return
        parsedXML = self._parsedXML(XMLMetadataFile)
        if (parsedXML is None): return
        field = parsedXML.find('//creator')
        if (field is not None): metadata.author = field.text
        field = parsedXML.find('//description')
        if (field is not None): metadata.comment = self._formatedHTMLPiece(field.text)
        field = parsedXML.find('//publisher')
        if (field is not None): metadata.company = field.text
        field = parsedXML.find('//date')
        if (field is not None): metadata.date = field.text[:10]
        field = parsedXML.find('//title')
        if (field is not None): metadata.title = field.text

    def _fetchHTMLMetadata( self, metadata, path ):
        try: xml = html.parse(path)
        except: return
        title = xml.find('.//title')
        if (title is None):
            title = xml.find('.//meta[@name="title"]')
            if (title is None): title = xml.find('.//meta[@property="og:title"]')
            if (title is None): title = xml.find('.//meta[@name="parsely-title"]')
            if (title is None): title = xml.find('.//name')
        if (title is not None): metadata.title = self._formatedString(title.text)
        author = xml.find('.//meta[@name="author"]')
        if (author is None): author = xml.find('.//meta[@property="og:author"]')
        if (author is None): author = xml.find('.//meta[@name="parsely-author"]')
        if (author is not None): metadata.author = author.get('content')
        comment = xml.find('.//meta[@name="description"]')
        if (comment is None):
            if (comment is None): comment = xml.find('.//meta[@property="og:description"]')
            if (comment is None): comment = xml.find('.//meta[@name="comment"]')
            if (comment is None): comment = xml.find('.//meta[@name="parselycomment"]')
        if (comment is not None): metadata.comment = self._formatedHTMLPiece(comment.get('content'))
        
    def _fetchMarkdownMetadata( self, metadata, path ):
        try: document = open(path, 'r')
        except: return
        title = [line for line in document if (re.match(r'^[\t ]*# .*$', line))]
        if (len(title) > 0): 
            metadata.title = re.sub(r'^[\t ]*# ', '', title[0]).strip()
            
    def _fetchOfficeOpenXMLMetadata( self, metadata, path ):
        try: document = ZIPFile(path, 'r')
        except: return
        try: 
            XMLMetadataFile = document.open('docProps/app.xml')
            parsedXML = self._parsedXML(XMLMetadataFile)
            if (parsedXML is None): return
            field = parsedXML.find('//Pages')
            if (field is None): field = parsedXML.find('//Slides')
            if (field is not None): metadata.pages = self._formatedString(field.text)
            field = parsedXML.find('//Company')
            if (field is not None): metadata.company = self._formatedString(field.text)
            XMLMetadataFile.close()
        except:
            pass
        try:
            XMLMetadataFile = document.open('docProps/core.xml')
            parsedXML = self._parsedXML(XMLMetadataFile)
            if (parsedXML is None): return
            field = parsedXML.find('//creator')
            if (field is not None): metadata.author = self._formatedString(field.text)
            field = parsedXML.find('//created')
            if (field is not None): metadata.date = self._formatedDate(field.text)
            field = parsedXML.find('//description')
            if (field is not None): metadata.comment = self._formatedHTMLPiece(field.text)
            field = parsedXML.find('//title')
            if (field is not None): metadata.title = self._formatedString(field.text)
            XMLMetadataFile.close()
        except:
            pass
            
    def _fetchOLECompoundFileMetadata( self, metadata, path ):
        try: 
            document = OLEFile(path)
            documentMetadata = document.get_metadata()
            document.close()
        except: 
            return
        encoding = documentMetadata.codepage if (documentMetadata.codepage > 0) else 1252
        encoding = 'cp' + str(encoding)
        if ((documentMetadata.author is not None) and (len(documentMetadata.author) > 1)):
            metadata.author = self._formatedString(documentMetadata.author, encoding)
        if (documentMetadata.comments is not None):
            metadata.comment = self._formatedStringList(documentMetadata.comments, encoding)
        if (documentMetadata.company is not None):
            metadata.company = self._formatedStringList(documentMetadata.company, encoding)
        if (documentMetadata.create_time is not None):
            metadata.date = documentMetadata.create_time.strftime('%Y-%m-%d')
        if (documentMetadata.category is not None):
            metadata.genre = self._formatedStringList(documentMetadata.category, encoding)
        if (documentMetadata.num_pages is not None):
            metadata.pages = str(documentMetadata.num_pages)
        elif (documentMetadata.slides is not None):
            metadata.pages = str(documentMetadata.slides)
        if ((documentMetadata.title is not None) and (len(documentMetadata.title) > 1)):
            metadata.title = self._formatedString(documentMetadata.title, encoding)

    def _fetchOpenDocumentMetadata( self, metadata, path ):
        with open(path, 'rb') as document:
            fileSignature = document.read(2)
            document.seek(0)
            if (fileSignature == b'<?'):
                try: parsedXML = self._parsedXML(document)
                except: return
            else:
                try: XMLMetadataFile = ZIPFile(path, 'r').open('meta.xml')
                except: return
                parsedXML = self._parsedXML(XMLMetadataFile)
            if (parsedXML is None): return
        field = parsedXML.find('//initial-creator')
        if (field is None): field = parsedXML.find('//creator')
        if (field is not None): metadata.author = self._formatedString(field.text)
        field = parsedXML.find('//description')
        if (field is not None): metadata.comment = self._formatedHTMLPiece(field.text)
        field = parsedXML.find('//creation-date')
        if (field is None): field = parsedXML.find('//date')
        if (field is not None): metadata.date = self._formatedDate(field.text[:10])
        field = parsedXML.find('//title')
        if (field is not None): metadata.title = self._formatedString(field.text)

    def _fetchPDFMetadata( self, metadata, path ):
        try: document = PDFFile(path, strict=False)
        except: return
        try:
            if (document.isEncrypted): return
            pages = document.numPages
            if (isinstance(pages, PDFIndirectObject)): pages = document.getObject(pages)
            metadata.pages = self._unicode(pages)
            info = document.documentInfo
            if (info is None): return
            author = info.get('/Author')
            if (isinstance(author, PDFIndirectObject)): author = document.getObject(author)
            metadata.author = self._formatedString(author) if (author is not None) else placeholder
            company = info.get('/EBX_PUBLISHER', placeholder)
            if (isinstance(company, PDFIndirectObject)): company = document.getObject(company)
            metadata.company = self._formatedString(company) if (company is not None) else placeholder
            date = info.get('/CreationDate')
            if (isinstance(date, PDFIndirectObject)): date = document.getObject(date)
            if (date is not None): metadata.date = self._formatedDate(date)
            title = info.get('/Title', placeholder)
            if (isinstance(title, PDFIndirectObject)): title = document.getObject(title)
            metadata.title = self._formatedString(title) if (title is not None) else placeholder
        except Exception as e:
            self.logMessage(str(e) + " :: " + str(sys.exc_info()[2].tb_lineno))

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FETCHING METADATA FROM IMAGES
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchUnspecifiedImageMetadata( self, metadata, path ):
        pass

    def _fetchImageMetadata( self, metadata, path ):
        try: image = Image.open(path, 'r')
        #except : # try other image reading methods
        except: return
        #metadata.channels = str(image.layers)
        #metadata.encoding = self._unicode(image.format, ignoreErrors=True)
        metadata.height = str(image.height)
        metadata.width = str(image.width)
        try: EXIF = image._getexif()
        except: EXIF = None
        image.close()
        if ((EXIF is None) or (len(EXIF) < 1)):
            self._fetchUnspecifiedImageMetadata(metadata, path)
            return
        cameraModel = EXIF.get(272, EXIF.get(50709, EXIF.get(50708, EXIF.get(271, EXIF.get(50735)))))
        cameraOwner = EXIF.get(42032)
        cameraOwner = (cameraOwner + ' (?)') if (cameraOwner is not None) else placeholder
        date = EXIF.get(36867, EXIF.get(36868, EXIF.get(306, EXIF.get(29, placeholder))))
        metadata.album = self._formatedString(EXIF.get(269, placeholder))
        metadata.author = self._formatedString(EXIF.get(315, EXIF.get(40093, cameraOwner)))
        metadata.comment = self._formatedStringList([EXIF.get(37510), EXIF.get(40092)])
        metadata.date = self._formatedDate(date[:10])
        if (cameraModel is not None): metadata.camera = self._formatedString(cameraModel)
        metadata.title = self._formatedString(EXIF.get(270, EXIF.get(40091, placeholder)))

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FETCHING METADATA FROM AUDIO/VIDEO
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchAPEv2Metadata( self, metadata, pathOrFile ):
        try: audio = mutagen.apev2.APEv2(pathOrFile)
        except: return
        metadata.album = self._formatedString(audio.get('Album', [placeholder])[0])
        metadata.artist = self._formatedStringList(audio.get('Artist', [placeholder]))
        author = audio.get('Composer')
        if (author is None):
            author = audio.get('Lyricist')
            if (author is None): author = audio.get('Writer')
        if (author is not None): metadata.author = self._formatedStringList(author)
        metadata.comment = self._formatedStringList(audio.get('Comment', [placeholder]))
        metadata.company = self._formatedStringList(audio.get('Label', [placeholder]))
        metadata.genre = self._formatedStringList(audio.get('Genre', [placeholder]))
        metadata.title = self._formatedString(audio.get('Title', [placeholder])[0])
        metadata.tracknumber = self._formatedTrackNumber(audio.get('Track', [placeholder])[0])
        metadata.date = self._formatedDate(audio.get('Year', [placeholder])[0][:10])

    def _fetchID3Metadata( self, metadata, pathOrFile ):
        try: audio = mutagen.id3.ID3(pathOrFile)
        except: return
        metadata.album = self._formatedString(audio.get('TALB', [placeholder])[0])
        metadata.artist = self._formatedStringList(audio.get('TPE1', [placeholder]))
        author = audio.get('TCOM')
        if (author is None): author = audio.get('TEXT')
        if (author is not None): metadata.author = self._formatedStringList(author)
        comments = [comment for comment in audio.getall('COMM') if (comment.desc == u'')]
        if (len(comments) > 0):
            comments = [self._unicode(comment, comment.encoding) for comment in comments]
            metadata.comment = self._formatedStringList(comments)
        metadata.company = self._formatedStringList(audio.get('TPUB', [placeholder]))
        metadata.genre = self._formatedStringList(audio.get('TCON', [placeholder]))
        metadata.title = self._formatedString(audio.get('TIT2', [placeholder])[0])
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRCK', [placeholder])[0])
        date = audio.get('TDRC')
        if (date is not None): date = date[0].get_text()[:10]
        else: date = audio.get('TYER', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)

    def _fetchUnspecifiedAVMetadata( self, metadata, path, complete = True ):
        try: av = MediaInfo.parse(path)
        except: return
        general = av.tracks[0]
        if (general.overall_bit_rate is not None): 
            metadata.bitrate = general.overall_bit_rate
            if (metadata.bitrate > 1024): metadata.bitrate = str(int(metadata.bitrate // 1000))
            else: metadata.bitrate = str(int(metadata.bitrate)) + ' bps'
        if (general.duration is not None): metadata.duration = self._formatedDuration(general.duration // 1000)
        elif (general.other_duration is not None): metadata.duration = general.other_duration[3][:8]
        for track in av.tracks:
            if (track.track_type[0] == 'V'):
                if (track.width is not None): metadata.width = str(track.width)
                if (track.height is not None): metadata.height = str(track.height)
            elif (track.track_type[0] == 'A'):
                if (track.sampling_rate is not None): metadata.samplerate = str(track.sampling_rate)
            elif (track.track_type[0] != 'G'): break
        if (not complete): return
        if (general.album is not None): metadata.album = self._formatedString(general.album)
        if (general.performer is not None): metadata.artist = self._formatedString(general.performer)
        if (general.director is not None): metadata.author = self._formatedString(general.director)
        elif (general.composer is not None): metadata.author = self._formatedString(general.composer)
        elif (general.lyricist is not None): metadata.author = self._formatedString(general.lyricist)
        elif (general.writer is not None): metadata.author = self._formatedString(general.writer)
        elif (general.writer is not None): metadata.author = self._formatedString(general.author)
        if (general.comment is not None): metadata.comment = self._formatedString(general.comment)
        if (general.publisher is not None): metadata.company = self._formatedString(general.publisher)
        if (general.genre is not None): metadata.genre = self._formatedString(general.genre)
        if (general.movie_name is not None): metadata.title = self._formatedString(general.movie_name)
        elif (general.track_name is not None): metadata.title = self._formatedString(general.track_name)
        elif (general.title is not None): metadata.title = self._formatedString(general.title)
        if (general.released_date is not None): date = self._formatedString(general.released_date)
        elif (general.recorded_date is not None): date = self._formatedString(general.recorded_date)
        else: date = placeholder
        metadata.date = self._formatedDate(general.released_date)
        if (general.track_name_position is not None):
            metadata.tracknumber = self._formatedTrackNumber(general.track_name_position)
            
    def _fetchFLACMetadata( self, metadata, pathOrFile ):
        try: audio = mutagen.flac.FLAC(pathOrFile)
        except: return
        metadata.album = audio.get('ALBUM', [placeholder])[0]
        metadata.artist = self._formatedStringList(audio.get('ARTIST', [placeholder]))
        author = audio.get('COMPOSER')
        if (author is None):
            author = audio.get('LYRICIST')
            if (author is None): author = audio.get('WRITER')
        if (author is not None): metadata.author = self._formatedStringList(author)
        metadata.bitrate = str(audio.info.bitrate // 1000)
        metadata.comment = self._formatedStringList(audio.get('COMMENT', [placeholder]))
        metadata.company = self._formatedStringList(audio.get('LABEL', [placeholder]))
        metadata.duration = self._formatedDuration(audio.info.length)
        metadata.genre = self._formatedStringList(audio.get('GENRE', [placeholder]))
        metadata.samplerate = str(audio.info.sample_rate)
        metadata.title = audio.get('TITLE', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRACKNUMBER', [placeholder])[0])
        date = audio.get('DATE', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        
    def _fetchMIDIMetadata( self, metadata, path ):
        with open(path, 'rb') as audio:
            fileData = audio.read()
            audio.seek(-32, 2)
            fileTail = audio.read(32)[:8]
            fileSize = audio.tell()
            audio.seek(0)            
            try: MIDIAudio = mutagen.smf.SMF(audio)
            except: return
            metadata.duration = self._formatedDuration(MIDIAudio.info.length + 1)
            metadata.bitrate = str(int((fileSize * 8) / (MIDIAudio.info.length + 1))) + ' bps'
            comments = re.findall('\xFF\x01.*?\x00', fileData)
            if (len(comments) > 0):
                comments = [self._cleanASCII(comment[2:-1]) for comment in comments]
                metadata.comment = self._formatedStringList(comments)
            names = re.findall('\xFF\x03.*?\x00', fileData)
            if(len(names) > 0):
                names = [self._cleanASCII(name[2:-1]) for name in names]
                metadata.title = self._formatedStringList(names)
            if (fileTail == b'APETAGEX'): self._fetchAPEv2Metadata(metadata, audio)
        
    def _fetchMP4Metadata( self, metadata, pathOrFile, fileSize = None ):
        try: av = mutagen.mp4.MP4(pathOrFile)
        except: return
        metadata.album = av.get('\xA9alb', [placeholder])[0]
        metadata.artist = self._formatedStringList(av.get('\xA9ART', [placeholder]))
        metadata.author = self._formatedStringList(av.get('\xA9wrt', [placeholder]))
        if (fileSize is not None):
            metadata.bitrate = str(int(fileSize // (self._parsedDuration(metadata.duration) * 125)))
        metadata.comment = self._formatedStringList(av.get('\xA9cmt', [placeholder]))
        metadata.company = self._formatedStringList(av.get('----:com.apple.iTunes:LABEL', [placeholder]))
        metadata.date = self._formatedDate(av.get('\xA9day', [placeholder])[0])
        metadata.duration = self._formatedDuration(av.info.length)
        metadata.genre = self._formatedStringList(av.get('\xA9gen', [placeholder]))
        metadata.samplerate = str(av.info.sample_rate)
        metadata.title = av.get('\xA9nam', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(str(av.get('trkn', [[None]])[0][0]))

    def _fetchOptimFROGMetadata( self, metadata, pathOrFile ):
        self._fetchAPEv2Metadata(metadata, pathOrFile)
        try: OptimFROGFile = mutagen.optimfrog.OptimFROG(pathOrFile)
        except: return
        metadata.duration = self._formatedDuration(OptimFROGFile.info.length)
        metadata.samplerate = str(OptimFROGFile.info.sample_rate)

    def _fetchAVMetadata( self, metadata, path ):
        with open(path, 'rb') as avfile:
            fileSignature = avfile.read(10)
            avfile.seek(-32, 2)
            fileTail = avfile.read(32)[:8]
            fileSize = avfile.tell()
            avfile.seek(0)
            if (fileSignature[:4] == b'fLaC'): 
                self._fetchFLACMetadata(metadata, avfile)
            elif (fileSignature[-6:] == b'ftypM4'): 
                self._fetchMP4Metadata(metadata, avfile)
            elif (fileSignature.startswith(b'OFR')): 
                self._fetchOptimFROGMetadata(metadata, avfile)
            elif (fileSignature[:3] == b'ID3'): 
                self._fetchID3Metadata(metadata, avfile)
                self._fetchUnspecifiedAVMetadata(metadata, path, complete=False)
            elif (fileTail == b'APETAGEX'): 
                self._fetchAPEv2Metadata(metadata, avfile)
                self._fetchUnspecifiedAVMetadata(metadata, path, complete=False)
            else: 
                self._fetchUnspecifiedAVMetadata(metadata, path)
            if ((metadata.bitrate == placeholder) and (metadata.duration != placeholder)):
                metadata.bitrate = str(fileSize // (self._parsedDuration(metadata.duration) * 125))
            # DSF, TTA, AAC

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FETCHING METADATA FROM PLAYLISTS AND SUBTITLES
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
            
    def _fetchSubRipMetadata( self, metadata, path ):
        with open(path, 'r') as subtitles:
            timeRegex = re.compile('[0-9][0-9]:[0-9][0-9]:[0-9][0-9],[0-9][0-9][0-9]')
            times = [line for line in subtitles if timeRegex.match(line)]
            size = subtitles.tell()
            if (len(times) > 0): 
                metadata.duration = times[-1].strip()[-12:-4]
                metadata.bitrate = str((size // self._parsedDuration(metadata.duration)) * 8) + ' bps'
            
    def _fetchXSPFMetadata( self, metadata, path ):
        with open(path, 'r') as playlist:
            try: parsedXML = self._parsedXML(playlist)
            except: return
            if (parsedXML is None): return
        field = parsedXML.find('//info')
        if (field is None): field = parsedXML.find('//description')
        if (field is None): field = parsedXML.find('//comment')
        if (field is not None): metadata.comment = self._formatedHTMLPiece(field.text)
        field = parsedXML.find('//title')
        if (field is not None): metadata.title = self._formatedString(field.text)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # FETCHING METADATA FROM OTHER KINDS OF FILES
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchDesktopEntryMetadata( self, metadata, path ):
        with open(path, 'r') as desktopEntry:
            for line in desktopEntry:
                line = line.split('=', 1)
                if (len(line) != 2): continue
                if (line[0] == 'Name'): metadata.title = self._formatedString(line[1])
                elif (line[0] == 'Comment'): metadata.comment = self._formatedString(line[1])
                elif (line[0] == 'Categories'): metadata.genre = self._formatedStringList(line[1].split(';'))
            
    def _fetchTorrentMetadata( self, metadata, path ):
        try: torrent = Torrent.from_file(path)
        except: return
        if (torrent.created_by is not None): metadata.author = torrent.created_by
        if (torrent.creation_date is not None): metadata.date = torrent.creation_date.isoformat()[:10]
        if (torrent.comment is not None): metadata.comment = self._formatedString(torrent.comment)
        if (torrent.name is not None): metadata.title = torrent.name
        
    def _fetchZIPMetadata( self, metadata, path ):
        try: archive = ZIPFile(path, 'r')
        except: return
        comment = self._unicode(archive.comment)
        if (len(comment) > 0): metadata.comment = self._formatedString(comment)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # DETERMINING AND USING THE PROPER FETCHING METHODS
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
        
    def _fetchNoMetadataAtAll( self, metadata, path ):
        pass
    
    def _fetchMagicallyIdentifiedMetadata( self, metadata, path ):
        fileSignature = None
        with open(path, 'r') as someFile: fileSignature = someFile.read(8)
        mappedMethod = self._signatureToMethodMap.get(fileSignature)
        if (mappedMethod is None): 
            mappedMethod = self._signatureToMethodMap.get(fileSignature[:4], self._fetchNoMetadataAtAll)
        mappedMethod(metadata, path)
        
    def _fetchMetadata( self, metadata, path, file = None ):
        mappedMethod = self._suffixToMethodMap.get(os.path.splitext(path)[-1][1:].lower())
        if (mappedMethod is not None): 
            mappedMethod(metadata, path)
        elif (file is not None):
            mime = file.get_mime_type()
            mappedMethod = self._mimeToMethodMap.get(mime)
            if (mappedMethod is not None): mappedMethod(metadata, path)
            elif (mime.startswith('ima')): self._fetchImageMetadata(metadata, path)
            elif (mime.startswith(('aud', 'vid'))): self._fetchAVMetadata(metadata, path)
            else: self._fetchMagicallyIdentifiedMetadata(metadata, path)
        else:
            self._fetchMagicallyIdentifiedMetadata(metadata, path)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # ASSIGNING THE FETCHED METADATA TO EACH FILE
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _assignNothingToFile( self, file ):
        file.add_string_attribute('album', placeholder)
        file.add_string_attribute('artist', placeholder)
        file.add_string_attribute('author', placeholder)
        file.add_string_attribute('bitrate', placeholder)
        file.add_string_attribute('camera', placeholder)
        file.add_string_attribute('comment', placeholder)
        file.add_string_attribute('company', placeholder)
        file.add_string_attribute('date', placeholder)
        file.add_string_attribute('dimensions', placeholder)
        file.add_string_attribute('duration', placeholder)
        file.add_string_attribute('genre', placeholder)
        file.add_string_attribute('height', placeholder)
        file.add_string_attribute('pages', placeholder)
        file.add_string_attribute('samplerate', placeholder)
        file.add_string_attribute('title', placeholder)
        file.add_string_attribute('tracknumber', placeholder)
        file.add_string_attribute('width', placeholder)
        file.add_string_attribute('year', placeholder)
        file.add_string_attribute('exif_flash', placeholder)

    def _assignMetadataToFile( self, metadata, file ):
        file.add_string_attribute('album', metadata.album)
        file.add_string_attribute('artist', metadata.artist)
        file.add_string_attribute('author', metadata.author)
        file.add_string_attribute('bitrate', metadata.bitrate +
            (' kbps' if ((metadata.bitrate != placeholder) and (metadata.bitrate[-1] != 's')) else ''))
        file.add_string_attribute('camera', metadata.camera)
        file.add_string_attribute('comment', metadata.comment)
        file.add_string_attribute('company', metadata.company)
        file.add_string_attribute('date', metadata.date)
        if (metadata.width != placeholder) and (metadata.height != placeholder):
            file.add_string_attribute('dimensions', (metadata.width + 'x' + metadata.height))
        else:
            file.add_string_attribute('dimensions', placeholder)
        file.add_string_attribute('duration', metadata.duration)
        file.add_string_attribute('genre', metadata.genre)
        file.add_string_attribute('height', metadata.height)
        file.add_string_attribute('pages', metadata.pages)
        file.add_string_attribute('samplerate', metadata.samplerate +
            (' Hz' if (metadata.samplerate != placeholder) else ''))
        file.add_string_attribute('title', metadata.title)
        file.add_string_attribute('tracknumber', metadata.tracknumber)
        file.add_string_attribute('width', metadata.width)
        file.add_string_attribute('year', metadata.date[:4])
        file.add_string_attribute('exif_flash', metadata.exif_flash)

    def _assignFetchedMetadataToFile( self, file, isLocal, status, path ):
        if (isLocal):
            isKnownJunk = self._knownJunk.get(status.st_ino, 0) >= status.st_mtime
            previousMetadata = self._knownFiles.get(status.st_ino, (0, None))
        else:
            isKnownJunk = status.st_size > maximumNonLocalFileSize
            previousMetadata = (0, None)
        if (isKnownJunk or (status.st_size <= 16)):
            self._assignNothingToFile(file)
        elif (previousMetadata[0] >= status.st_mtime):
            self._assignMetadataToFile(previousMetadata[1], file)
        else:
            metadata = fileMetadata()
            self._mute() # Muting to hide possible third-party complaints
            try:
                self._fetchMetadata(metadata, path, file)
            except Exception as someException:
                if (not isinstance(someException, IOError)): self._logException(someException, path)
                self._assignNothingToFile(file)
            else:
                self._assignMetadataToFile(metadata, file)
                if (isLocal): self._remember(metadata, status)
            self._unmute()

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # PREFETCHING METADATA
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def prefetchMetadata( self, path ):
        try: status = os.stat(path)
        except: return
        if ((not os.path.isfile(path)) or (status.st_size <= 16)): return
        if (self._knownJunk.get(status.st_ino, 0) >= status.st_mtime): return
        if (self._knownFiles.get(status.st_ino, (0, None))[0] >= status.st_mtime): return
        sys.__stdout__.write("Prefetching metadata from '" + path + "'\n")
        metadata = fileMetadata()
        self._mute() # Muting to hide possible third-party complaints
        try: self._fetchMetadata(metadata, path, None)
        except IOError: pass
        except Exception as someException: self._logException(someException, path)
        else: self._remember(metadata, status)
        self._unmute()
    
    def massPrefetch( self, basePath = '/', recursively = False ):
        if (not os.path.isdir(basePath)):
            self.logMessage("'" + basePath + "' is not a directory", True)
            return
        if (basePath[-1] != '/'): basePath += '/'
        try:
            if (recursively):
                for root, dirs, files in os.walk(basePath):
                    for path in files: self.prefetchMetadata(os.path.realpath(basePath + path))
            else:
                for path in os.listdir(basePath): 
                    self.prefetchMetadata(os.path.realpath(basePath + path))
        except Exception as someException:
            self._logException(someException, basePath)

    def _keepFoldersPrefetched( self ):
        while True:
            folder = self._foldersToPrefetch.get()
            if folder is None: continue
            self.massPrefetch(folder)
            self._foldersToPrefetch.task_done()

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # HANDLING (PRELIMINARILY) OR SKIPPING EACH FILE
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _usablePath( self, file ):
        scheme = file.get_uri_scheme()
        if (self._gvfsMountpointsDirExists):
            uri = file.get_uri().split('/')
            if (scheme == 'mtp'):
                uri = uri[0] + 'host=' + uri[2].replace(',', '%2C') + '/' + unquote('/'.join(uri[3:]))
                return (self._gvfsMountpointsDir + uri)
            elif (scheme == 'smb'):
                uri = uri[2] + ',share=' + unquote(uri[3]) + '/' + unquote('/'.join(uri[4:]))
                uri = 'smb-share:server=' + uri
                return (self._gvfsMountpointsDir + uri)
        self.logMessage("Unable to handle " + scheme + ":// URIs", True)
        return ''

    def update_file_info( self, file ):
        if (file.get_uri_scheme() == 'file'):
            path = os.path.realpath(unquote(file.get_uri()[7:]))
            isLocal = True
        else:
            path = self._usablePath(file)
            isLocal = False
        try:
            status = os.stat(path)
            file.add_string_attribute('inode', str(status.st_ino))
            fileType = file.get_file_type()
        except:
            file.add_string_attribute('inode', placeholder)
            fileType = 0
        if (fileType == 1):
            self._assignFetchedMetadataToFile(file, isLocal, status, path)
        else:
            if ((fileType == 2) and (prefetchSubfolders)): self._foldersToPrefetch.put(path)
            self._assignNothingToFile(file)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # ADDING THE EXTRA COLUMNS TO NAUTILUS
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def get_columns( self ):
        self.logMessage("Adding extra columns...")
        return (
            Nautilus.Column(name='Metanautilus::inode_col',        attribute='inode',
                label="Index Node",         description="Index Node of the file"),
            Nautilus.Column(name='Metanautilus::album_col',        attribute='album',
                label="Album",              description="The album the work is part of"),
            Nautilus.Column(name='Metanautilus::artist_col',       attribute='artist',
                label="Artist",             description="Artist of the work"),
            Nautilus.Column(name='Metanautilus::author_col',       attribute='author',
                label="Author",             description="Author of the work"),
            Nautilus.Column(name='Metanautilus::bitrate_col',      attribute='bitrate',
                label="Bit Rate",           description="Overall bitrate"),
            Nautilus.Column(name='Metanautilus::camera_col',       attribute='camera',
                label="Camera Model",       description="Camera model used to take the picture"),
            Nautilus.Column(name='Metanautilus::comment_col',      attribute='comment',
                label="Comment",            description="Comment"),
            Nautilus.Column(name='Metanautilus::company_col',      attribute='company',
                label="Company",            description="Company"),
            Nautilus.Column(name='Metanautilus::date_col',         attribute='date',
                label="Date",               description="Year, Month and Day"),
            Nautilus.Column(name='Metanautilus::dimensions_col',   attribute='dimensions',
                label="Dimensions",         description="Actual pixel dimensions"),
            Nautilus.Column(name='Metanautilus::duration_col',     attribute='duration',
                label="Duration",           description="Audio or video duration"),
            Nautilus.Column(name='Metanautilus::exif_flash_col',   attribute='exif_flash',
                label="Flash (EXIF)",       description="Flash mode (EXIF)"),
            Nautilus.Column(name='Metanautilus::genre_col',        attribute='genre',
                label="Genre",              description="Genre of the work"),
            Nautilus.Column(name='Metanautilus::height_col',       attribute='height',
                label="Height",             description="Actual pixel height"),
            Nautilus.Column(name='Metanautilus::pages_col',        attribute='pages',
                label="Pages",              description="Page count of the document"),
            Nautilus.Column(name='Metanautilus::samplerate_col',   attribute='samplerate',
                label="Sample Rate",        description="Audio sample rate"),
            Nautilus.Column(name='Metanautilus::title_col',        attribute='title',
                label="Title",              description="Title of the work"),
            Nautilus.Column(name='Metanautilus::tracknumber_col',  attribute='tracknumber',
                label="#",                  description="Track number"),
            Nautilus.Column(name='Metanautilus::width_col',        attribute='width',
                label="Width",              description="Actual pixel width"),
            Nautilus.Column(name='Metanautilus::year_col',         attribute='year',
                label="Year",               description="Year"),
        )

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # INITIALIZING THE EXTENSION
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _loadMapping( self, mapFileName ):
        mapping = dict()
        for dataFolder in os.getenv('XDG_DATA_DIRS', '').split(':'):
            mapFilePath = dataFolder + '/metanautilus/' + mapFileName
            if (os.path.isfile(mapFilePath)):
                try: 
                    mapFile = open(mapFilePath, 'r')
                except:
                    self.logMessage("Could not load " + mapFileName + "...", True)
                else:
                    for line in mapFile:
                        if ((len(line) < 8) or (line[0] == ' ') or (line[-1] == ' ')): continue
                        keyAndMethod = line.split(' ')
                        key = eval('\'' + keyAndMethod[0] + '\'')
                        mapping[key] = eval('self.' + keyAndMethod[-1])
                    mapFile.close()
                    return mapping
        self.logMessage("Could not find " + mapFileName + "...", True)
        return mapping

    def _loadOrCreateCache( self, cacheDir ):
        self._knownFiles = dict()
        self._knownJunk = dict()
        if (not os.path.isdir(cacheDir)):
            try: 
                os.makedirs(name=cacheDir)
            except OSError as someException:
                if (not ((someException.errno == errno.EEXIST) and os.path.isdir(path))):
                    self.logMessage("Failed to create cache folder", True)
                    return
        if (os.path.isfile(self._cacheFile)):
            try:
                with open(self._cacheFile, 'rb') as cacheHandle: 
                    self._knownFiles = loadPickle(cacheHandle)
            except EOFError: 
                pass
        else:
            with open(self._cacheFile, 'a'): pass
        if (os.path.isfile(self._junkCacheFile)):
            try:
                with open(self._junkCacheFile, 'rb') as cacheHandle: 
                    self._knownJunk = loadPickle(cacheHandle)
            except EOFError: 
                pass
        else:
            with open(self._junkCacheFile, 'a'): pass

    def _initializeCache( self ):
        cacheDir = os.getenv("HOME") + '/.cache/metanautilus/'
        self._cacheFile = cacheDir + 'known-metadata'
        self._junkCacheFile = cacheDir + 'known-junk'
        self._loadOrCreateCache(cacheDir)
        self._knownMetadataMutex = Lock()
        self._knownJunkMutex = Lock()
        self._unpickledKnownFiles = 0
        self._unpickledKnownJunk = 0
        pickler = Thread(target=self._keepKnownInformationPickled)
        pickler.daemon = True
        pickler.start()
        
    def _initializeFoldersPrefetcher( self ):
        self._foldersToPrefetch = queue()
        foldersPrefetcher = Thread(target=self._keepFoldersPrefetched)
        foldersPrefetcher.daemon = True
        foldersPrefetcher.start()
        
    def __init__( self ):
        self.logMessage("Initializing [Python " + sys.version.partition(' (')[0] + "]")
        self._lastWarning = ""
        self._suffixToMethodMap = self._loadMapping('suffixToMethod.map')
        self._mimeToMethodMap = self._loadMapping('mimeToMethod.map')
        self._signatureToMethodMap = self._loadMapping('signatureToMethod.map')
        self._gvfsMountpointsDir = '/run/user/' + str(os.getuid()) + '/gvfs/'
        self._gvfsMountpointsDirExists = os.path.isdir(self._gvfsMountpointsDir)
        self._initializeCache()
        self._initializeFoldersPrefetcher()

# =============================================================================================

if (__name__ == '__main__'):
    pass #TODO

# =============================================================================================
