#!/usr/bin/python3

# =============================================================================================

# In order to have this script working (if it is currently not),
# run 'install.sh -3' (should come with this script)

# IF YOU WILL BE RUNNING THIS NOT ON UBUNTU...
# #1 Install Mutagen, pyexiv2, Kaa Metadata and pypdf (Python 3 modules)
# #2 Install python-nautilus via your package manager
# #3 Check where python-nautilus extension must be placed in your system
#     and place a copy of this python script there with execute permission

# =============================================================================================
 
import sys, os
from threading import Thread, activeCount, Lock
from datetime import datetime
from time import sleep
from urllib import unquote
from pickle import dump, load, HIGHEST_PROTOCOL
if (sys.version[0] <= '2'): 
    pythonIs2OrOlder = True
    import Queue as queue
else: 
    pythonIs2OrOlder = False
    import queue as queue

from gi import require_version       # Nautilus stuff
require_version("Gtk", "3.0")        # 
require_version('Nautilus', '3.0')   # ...
from gi.repository import GLib, Nautilus, GObject, Gtk
GLib.threads_init()
GObject.threads_init()

import lxml.html                     # for reading XML/HTML

import zipfile

from PIL import Image                # for reading image
import pyexiv2                       # for reading EXIF metadata

from pymediainfo import MediaInfo
import mutagen.flac, mutagen.mp4
import mutagen.smf
import mutagen.id3, mutagen.mp3, mutagen.aac, mutagen.aiff, mutagen.dsf, mutagen.trueaudio
import mutagen.apev2, mutagen.monkeysaudio, mutagen.musepack, mutagen.optimfrog, mutagen.wavpack

from PyPDF2 import PdfFileReader     # for reading PDF
from ebooklib import epub            # for reading EPUB

from torrentool.api import Torrent

# =============================================================================================

placeholder = "-"
minFilesToCache = 20
ignoreNonLocalFiles = False
maximumNonLocalFileSize = 268435456 # 256MB

# =============================================================================================

class fileMetadata():
    def __init__( self ):
        self.album = placeholder
        self.artist = placeholder
        self.author = placeholder
        self.bitrate = placeholder
        self.camera = placeholder
        self.comment = placeholder
        self.date = placeholder
        self.duration = placeholder
        self.genre = placeholder
        self.height = placeholder
        self.pages = placeholder
        self.samplerate = placeholder
        self.title = placeholder
        self.tracknumber = placeholder
        self.width = placeholder
        self.year = placeholder
        self.exif_flash = placeholder
    
    def nonBlankFields( self ):
        nonBlankCount = 0
        if self.album != placeholder: nonBlankCount += 1
        if self.artist != placeholder: nonBlankCount += 1
        if self.author != placeholder: nonBlankCount += 1
        if self.bitrate != placeholder: nonBlankCount += 1
        if self.camera != placeholder: nonBlankCount += 1
        if self.comment != placeholder: nonBlankCount += 1
        if self.date != placeholder: nonBlankCount += 1
        if self.duration != placeholder: nonBlankCount += 1
        if self.genre != placeholder: nonBlankCount += 1
        if self.height != placeholder: nonBlankCount += 1
        if self.pages != placeholder: nonBlankCount += 1
        if self.samplerate != placeholder: nonBlankCount += 1
        if self.title != placeholder: nonBlankCount += 1
        if self.tracknumber != placeholder: nonBlankCount += 1
        if self.width != placeholder: nonBlankCount += 1
        if self.year != placeholder: nonBlankCount += 1
        if self.exif_flash != placeholder: nonBlankCount += 1
        return nonBlankCount

# =============================================================================================

class Metanautilus( GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider ):

    def _unmute( self ):
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__
        
    def _mute( self ):
        try: sys.stderr = sys.stdout = open(os.devnull, 'w')
        except: self._unmute()

    def _logMessage( self, message, isWarning = False ):
        if (isWarning): 
            if (self._lastWarning == message): return
            self._lastWarning = message
            sys.stdout.write("Metanautilus-\x1B[33;1mWARNING\x1B[0;0m: ")
        else: 
            sys.stdout.write("Metanautilus: ")
        now = datetime.now()
        prettyTime = ("{:%H:%M:%S.}".format(now) + str(now.microsecond * 1000))[:12]
        sys.stdout.write("\x1B[34m" + prettyTime + "\x1B[0m: " + message + "\n")

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _pickleKnownMetadata( self, cacheFile ):
        self._logMessage("Pickling currently known metadata...")
        self._knownMetadataMutex.acquire()
        if not os.path.exists(cacheFile) or os.path.isfile(cacheFile):
            with open(cacheFile, 'wb') as cacheHandle:
                try: dump(self._knownFiles, cacheHandle, protocol=HIGHEST_PROTOCOL)
                except PickleError: self._logMessage("Failed to pickle known metadata...")
        self._unpickledKnownFiles = 0
        self._knownMetadataMutex.release()
    
    def _pickleKnownJunk( self, junkCacheFile ):
        self._logMessage("Pickling list of currently known junk...")
        self._knownJunkMutex.acquire()
        if not os.path.exists(junkCacheFile) or os.path.isfile(junkCacheFile):
            with open(junkCacheFile, 'wb') as cacheHandle:
                try: dump(self._knownJunk, cacheHandle, protocol=HIGHEST_PROTOCOL)
                except PickleError: self._logMessage("Failed to pickle known junk list...")
        self._unpickledKnownFiles = 0
        self._knownJunkMutex.release()

    def _keepKnownInformationPickled( self, cacheFile, junkCacheFile ):
        cycle = 0
        while True:
            sleep(3)
            if (self._unpickledKnownFiles > 0):
                if (not os.path.exists(cacheFile)):
                    self._logMessage("Forgetting all metadata (pickle file removed)...")
                    self._knownMetadataMutex.acquire()
                    self._knownFiles = dict()
                    self._unpickledKnownFiles = 0
                    self._knownMetadataMutex.release()
                    with open(cacheFile, 'a'): pass
                elif (self._unpickledKnownFiles > minFilesToCache) or ((cycle % 10) == 0): 
                    self._pickleKnownMetadata(cacheFile)
            if (self._unpickledKnownJunk > 0):
                if (not os.path.exists(junkCacheFile)):
                    self._logMessage("Forgetting all known junk (pickle file removed)...")
                    self._knownJunkMutex.acquire()
                    self._knownJunk = dict()
                    self._unpickledKnownJunk = 0
                    self._knownJunkMutex.release()
                    with open(junkCacheFile, 'a'): pass
                elif (self._unpickledKnownJunk > minFilesToCache) or ((cycle % 10) == 0): 
                    self._pickleKnownJunk(junkCacheFile)
            if (cycle == 1000): cycle = 1
            else: cycle += 1
            sleep(12)
            
    def _rememberMetadata( self, metadata, fileStatus ):
        self._knownMetadataMutex.acquire()
        self._knownFiles[fileStatus.st_ino] = (fileStatus.st_mtime, metadata)
        self._unpickledKnownJunk += 1
        self._knownMetadataMutex.release()
            
    def _rememberJunk( self, fileStatus ):
        self._knownJunkMutex.acquire()
        self._knownJunk[fileStatus.st_ino] = fileStatus.st_mtime
        self._unpickledKnownFiles += 1
        self._knownJunkMutex.release()
        
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _formatedDate( self, dateString ):
        size = len(dateString)
        if (size >= 10): return dateString[:10]
        elif (size == 4): return dateString + '-??-??'
        elif (size == 7): return dateString + '-??'
        else: return placeholder

    def _formatedDuration( self, secs ):
        return '%02i:%02i:%02i' % ((int(secs/3600)), (int(secs/60%60)), (int(secs%60)))
        
    def _formatedList( self, stringList ):
        try:
            if len(stringList) == 1: return str(stringList[0]).replace('\x00', '').replace('\n', '')
            elif len(stringList) == 0: return placeholder
            finalString = ''
            for item in stringList: finalString += str(item) + '; '
            return finalString.replace('\x00', r'').replace('\n', r'')[:-1]
        except TypeError:
            return str(stringList)
        
    def _formatedNumber( self, numberString ):
        finalString = ''
        for c in numberString:
            if (c > '9') or (c < '0'): finalString += c
        return finalString
        
    def _formatedString( self, anyString ):
        return str(anyString).replace('\x00', r'').replace('\n', r'')
        
    def _formatedTrackNumber( self, trackNumberString ):
        pos = 0
        for c in trackNumberString:
            if (c > '9') or (c < '0'): break
            pos += 1
        if pos == 0: return placeholder
        elif pos == 1: return '0' + trackNumberString[0]
        return trackNumberString[:pos]
        
    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _fetchTorrentMetadata( self, metadata, path ):
        try: torrent = Torrent.from_file(path)
        except: return
        if torrent.created_by is not None: metadata.author = torrent.created_by
        if torrent.creation_date is not None: 
            metadata.date = torrent.creation_date.isoformat()[:10]
            metadata.year = metadata.date[:4]
        if torrent.comment is not None: metadata.comment = torrent.comment
        if torrent.name is not None: metadata.title = torrent.name
    
    def _fetchHTMLMetadata( self, metadata, path ):
        try: xml = lxml.html.parse(path)
        except: return
        title = xml.find('.//title')
        if title is None: 
            title = xml.find('.//meta[@name="title"]')
            if title is None: title = xml.find('.//meta[@property="og:title"]')
            if title is None: title = xml.find('.//meta[@name="parsely-title"]')
            if title is None: title = xml.find('.//name')
        if title is not None: metadata.title = title.text
        author = xml.find('.//meta[@name="author"]')
        if author is None: author = xml.find('.//meta[@property="og:author"]')
        if author is None: author = xml.find('.//meta[@name="parsely-author"]')
        if author is not None: metadata.author = author.get('content')
        comment = xml.find('.//meta[@name="description"]')
        if comment is None: comment = xml.find('.//meta[@property="og:description"]')
        if comment is None: comment = xml.find('.//meta[@name="comment"]')
        if comment is None: comment = xml.find('.//meta[@name="parselycomment"]')
        if comment is not None: metadata.comment = comment.get('content') 
        
    def _fetchDesktopEntryMetadata( self, metadata, path ):
        with open(path, 'r') as textfile:
            for line in myfile:
                key, value = line.split('=', 1)
                if (key == 'Name'): metadata.title = value
                elif (key == 'Comment'): metadata.comment = value
                elif (key == 'Categories'): metadata.genre = value.replace(';', '; ')
            if (metadata.genre[-2:] == '; '): metadata.genre = metadata.genre[:-2]
        
    def _fetchPDFMetadata( self, metadata, path ):
        with open(path, 'rb') as documentFile:
            try: document = PdfFileReader(documentFile)
            except: return
            if document.isEncrypted: return
            try: metadata.pages = str(document.getNumPages())
            except: pass
            try: info = document.documentInfo()
            except: return
            metadata.author = info.get('/Author', placeholder)
            metadata.title = info.get('/Title', placeholder)

    def _fetchEPUBMetadata( self, metadata, path ):
        try: document = epub.read_epub(path)
        except Exception as e: sys.stderr.write(str(e))

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readID3( self, metadata, file ):
        try: audio = mutagen.id3.ID3(file)
        except: return
        metadata.album = audio.get('TALB', [placeholder])[0]
        metadata.artist = self._formatedList(audio.get('TPE1', [placeholder]))
        author = audio.get('TCOM')
        if author is None: author = audio.get('TEXT')
        if author is not None: metadata.author = self._formatedList(author)
        comments = []
        for COMMFrame in audio.getall('COMM'):
            if COMMFrame.desc == u'': comments.append(COMMFrame)
        metadata.comment = self._formatedList(comments)
        metadata.genre = self._formatedList(audio.get('TCON', [placeholder]))
        metadata.title = audio.get('TIT2', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRCK', [placeholder])[0])
        date = audio.get('TDRC')
        if date is not None: date = date[0].get_text()[:10]
        else: date = audio.get('TYER', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchMP4Metadata( self, metadata, file ):
        try: av = mutagen.mp4.MP4(file)
        except: return    
        metadata.album = av.get('\xA9alb', [placeholder])[0]
        metadata.artist = self._formatedList(av.get('\xA9ART', [placeholder]))
        metadata.author = self._formatedList(av.get('\xA9wrt', [placeholder]))
        metadata.bitrate = str(av.info.bitrate / 1000)
        metadata.comment = self._formatedList(av.get('\xA9cmt', [placeholder]))
        metadata.date = self._formatedDate(av.get('\xA9day', [placeholder])[0])
        metadata.duration = self._formatedDuration(av.info.length)
        metadata.genre = self._formatedList(av.get('\xA9gen', [placeholder]))
        metadata.samplerate = str(av.info.sample_rate)
        metadata.title = av.get('\xA9nam', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(str(av.get('trkn', [[None]])[0][0]))
        metadata.year = av.get('\xA9day', [placeholder])[0][:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchFLACMetadata( self, metadata, fileObject ):
        try: audio = mutagen.flac.FLAC(fileObject)
        except: return
        metadata.album = audio.get('ALBUM', [placeholder])[0]
        metadata.artist = self._formatedList(audio.get('ARTIST', [placeholder]))
        author = audio.get('COMPOSER')
        if author is None: 
            author = audio.get('LYRICIST')
            if author is None: author = audio.get('WRITER')
        if author is not None: metadata.author = self._formatedList(author)
        metadata.bitrate = str(audio.info.bitrate / 1000)
        metadata.comment = self._formatedList(audio.get('COMMENT', [placeholder]))
        metadata.duration = self._formatedDuration(audio.info.length)
        metadata.genre = self._formatedList(audio.get('GENRE', [placeholder]))
        metadata.samplerate = str(audio.info.sample_rate)
        metadata.title = audio.get('TITLE', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRACKNUMBER', [placeholder])[0])
        date = audio.get('DATE', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readAPEv2( self, metadata, file, signature ):
        audio = None
        try: 
            if signature.startswith(b'MAC'): audio = mutagen.monkeysaudio.MonkeysAudio(file)
            elif signature.startswith(b'MPCK'): audio = mutagen.musepack.Musepack(file)
            elif signature.startswith(b'OFR'): audio = mutagen.optimfrog.OptimFROG(file)
            elif signature.startswith(b'wvpk'): audio = mutagen.wavpack
            #else self._readUnspecifiedAVFormat(metadata, 
            metadata.samplerate = str(audio.info.sample_rate)
            metadata.duration = self._formatedDuration(audio.info.length)
        except mutagen.MutagenError:
            try: audio = mutagen.apev2.APEv2(file)
            except: return
            knownFileType = False
        metadata.album = audio.get('Album', [placeholder])[0]
        metadata.artist = self._formatedList(audio.get('Artist', [placeholder]))
        author = audio.get('Composer')
        if author is None: 
            author = audio.get('Lyricist')
            if author is None: author = audio.get('Writer')
        if author is not None: metadata.author = self._formatedList(author)
        metadata.comment = self._formatedList(audio.get('Comment', [placeholder]))
        metadata.genre = self._formatedList(audio.get('Genre', [placeholder]))
        metadata.title = audio.get('Title', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('Track', [placeholder])[0])
        date = audio.get('Year', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readUnspecifiedAVFormat( self, metadata, path, complete=True ):
        try: av = MediaInfo.parse(path)
        except: return
        general = av.tracks[0]
        if general.overall_bit_rate is not None: metadata.bitrate = str(int(general.overall_bit_rate / 1000))
        if general.duration is not None: metadata.duration = self._formatedDuration(general.duration / 1000)
        elif general.other_duration is not None: metadata.duration = general.other_duration[3][:8]
        for track in av.tracks:
            if track.track_type[0] == 'V':
                if track.width is not None: metadata.width = str(track.width)
                if track.height is not None: metadata.height = str(track.height)
            elif track.track_type[0] == 'A':
                if track.sampling_rate is not None: metadata.samplerate = str(track.sampling_rate)
            elif track.track_type[0] != 'G': break
        if (not complete): return
        if general.album is not None: metadata.album = general.album
        if general.performer is not None: metadata.artist = general.performer
        if general.director is not None: metadata.author = general.director
        elif general.composer is not None: metadata.author = general.composer
        elif general.lyricist is not None: metadata.author = general.lyricist
        elif general.writer is not None: metadata.author = general.writer
        if general.comment is not None: metadata.comment = general.comment
        if general.genre is not None: metadata.genre = general.genre
        if general.movie_name is not None: metadata.title = general.movie_name
        elif general.track_name is not None: metadata.title = general.track_name
        elif general.title is not None: metadata.title = general.title
        if general.released_date is not None: 
            metadata.date = self._formatedDate(general.released_date)
            metadata.year = metadata.date[:4]
        elif general.recorded_date is not None: 
            metadata.date = self._formatedDate(general.recorded_date)
            metadata.year = metadata.date[:4]
        if general.track_name_position is not None: 
            metadata.tracknumber = self._formatedTrackNumber(general.track_name_position)
        

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchAVMetadata( self, metadata, path, mime ):
        isVideo = mime[0] == 'v'
        with open(path, 'rb') as avfile:
            filesig = avfile.read(8)
            avfile.seek(os.stat(path).st_size - 32)
            filetail = avfile.read(8)
            avfile.seek(0)
            if filesig.startswith(b'fLa'): 
                self._fetchFLACMetadata(metadata, avfile)
            elif filesig.endswith(b'ftyp') and not isVideo: 
                self._fetchMP4Metadata(metadata, avfile)
            elif filesig.startswith(b'ID3'): 
                self._readID3(metadata, avfile)
                self._readUnspecifiedAVFormat(metadata, path, complete=False)
            elif filetail == b'APETAGEX': 
                self._readAPEv2(metadata, avfile, filesig)
            else:
                self._readUnspecifiedAVFormat(metadata, path)
            #if mime.endswith(('/mpeg', 'mp2')): # audio/mpeg, audio/x-mp2
            #    info = mutagen.mp3.MPEGInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000)
            #elif mime.endswith('/aac'): # audio/aac
            #    info = mutagen.aac.AACInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000)
            #elif mime.endswith('aiff'): # audio/x-aiff
            #    info = mutagen.aiff.AIFFInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000)
            #metadata.samplerate = str(info.sample_rate)
            #metadata.duration = self._formatedDuration(info.length)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchImageMetadata( self, metadata, path, mime ):
        try:
            image = pyexiv2.ImageMetadata(path)
            image.read()
            try:
                metadata.date = str(image['Exif.Photo.DateTimeOriginal'].raw_value)
                metadata.date = metadata.date[:10].replace(':', '-')
                metadata.year = metadata.date[:4]
            except: pass
            try: metadata.camera = str(image['Exif.Image.Model'].raw_value)
            except: pass
            try: metadata.exif_flash = str(image['Exif.Photo.Flash'].raw_value)
            except: pass
        except: 
            pass
        try:
            image = Image.open(path)
            metadata.width = str(image.size[0])
            metadata.height = str(image.size[1])
        except:
            pass

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _assignNothingToFile( self, file ):
        file.add_string_attribute('album', placeholder)
        file.add_string_attribute('artist', placeholder)
        file.add_string_attribute('author', placeholder)
        file.add_string_attribute('bitrate', placeholder)
        file.add_string_attribute('camera', placeholder)
        file.add_string_attribute('comment', placeholder)
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
        
    def _assignMetadataToFile( self, file, metadata ):
        file.add_string_attribute('album', metadata.album)
        file.add_string_attribute('artist', metadata.artist)
        file.add_string_attribute('author', metadata.author)
        file.add_string_attribute('bitrate', metadata.bitrate + 
            (' kbps' if (metadata.bitrate != placeholder) else ''))
        file.add_string_attribute('camera', metadata.camera)
        file.add_string_attribute('comment', metadata.comment)
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
        file.add_string_attribute('year', metadata.year)
        file.add_string_attribute('exif_flash', metadata.exif_flash)

    def _fetchMetadataThenAssignToFile( self, file, isLocal, status, path ):
        if (isLocal):
            isKnownJunk = self._knownJunk.get(status.st_ino) >= status.st_mtime
            previousMetadata = self._knownFiles.get(status.st_ino)
        else:
            isKnownJunk = status.st_size > maximumNonLocalFileSize
            previousMetadata = None 
            
        if (isKnownJunk or (status.st_size <= 16)):
            self._assignNothingToFile(file)
        elif ((previousMetadata is not None) and (previousMetadata[0] >= status.st_mtime)):
            self._assignMetadataToFile(file, previousMetadata[1])
        else:
            metadata = fileMetadata() 
            mime = file.get_mime_type()
            self._mute() # Muting to hide possible third-party complaints
            if mime.startswith('ima'):
                self._fetchImageMetadata(metadata, path, mime)
            elif mime.startswith(('aud', 'vid')):
                self._fetchAVMetadata(metadata, path, mime)
            elif path.endswith(('.ofr', '.ofs', '.rmvb', '.rm', '.ram')):
                self._fetchAVMetadata(metadata, path, mime)
            elif path.endswith(('.html', '.xhtml', '.htm')):
                self._fetchHTMLMetadata(metadata, path)
            elif path.endswith('.desktop'):
                self._fetchDesktopEntryMetadata(metadata, path)
            elif mime.startswith('app'):
                mime = mime[12:]
                if mime.endswith('pdf'): self._fetchPDFMetadata(metadata, path)
                elif mime.startswith('epub'): self._fetchEPUBMetadata(metadata, path)
                elif mime.endswith('torrent'): self._fetchTorrentMetadata(metadata, path)
            self._unmute()
            self._assignMetadataToFile(file, metadata)
            if (isLocal):
                if (metadata.nonBlankFields() == 0): self._rememberJunk(status)
                else: self._rememberMetadata(metadata, status)
        
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
            #elif (scheme == 'archive'): # Doesn't work as the other cases
            #    uri = 'archive:host=' + uri[2] + '/' + unquote('/'.join(uri[3:]))
            #    return (self._gvfsMountpointsDir + uri)
        self._logMessage("Unable to handle " + scheme + ":// URIs", isWarning=True)
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
        if (fileType == 1): self._fetchMetadataThenAssignToFile(file, isLocal, status, path)
        elif (fileType == 2): self._assignNothingToFile(file) # TODO: prefetch dir's content
        else: self._assignNothingToFile(file)

    def get_columns( self ):
        self._logMessage("Adding extra columns...")
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
    
    def _loadOrCreateCache( self, cacheDir, cacheFile, junkCacheFile ):
        if not (os.path.exists(cacheDir) and os.path.isdir(cacheDir)):
            try: os.makedirs(name=cacheDir)
            except OSError as e:
                if (e.errno == errno.EEXIST) and os.path.isdir(path): 
                    pass
                else: 
                    self._logMessage("Failed to create cache folder", isWarning=True)
                    return
        if os.path.exists(cacheFile) and os.path.isfile(cacheFile):
            try:  
                with open(cacheFile, 'rb') as cacheHandle: self._knownFiles = load(cacheHandle)
            except EOFError:
                self._knownFiles = dict()
        else:
            with open(cacheFile, 'a'): pass
            self._knownFiles = dict()
        if os.path.exists(junkCacheFile) and os.path.isfile(junkCacheFile):
            try:
                with open(junkCacheFile, 'rb') as cacheHandle: self._knownJunk = load(cacheHandle)
            except EOFError:
                self._knownJunk = dict()
        else:
            with open(junkCacheFile, 'a'): pass
            self._knownJunk = dict()
            
    def _initializeCache( self ):
        cacheDir = os.getenv("HOME") + '/.cache/metanautilus/'
        cacheFile = cacheDir + 'known-metadata'
        junkCacheFile = cacheDir + 'known-junk'        
        self._loadOrCreateCache(cacheDir, cacheFile, junkCacheFile)
        self._knownMetadataMutex = Lock()
        self._knownJunkMutex = Lock()
        self._unpickledKnownFiles = 0
        self._unpickledKnownJunk = 0
        pickler = Thread(target=self._keepKnownInformationPickled, args=(cacheFile,junkCacheFile))
        pickler.daemon = True
        pickler.start()

    def __init__( self ):
        self._logMessage("Initializing [Python " + sys.version.partition(' (')[0] + "]")
        self._lastWarning = ""
        self._gvfsMountpointsDir = '/run/user/' + str(os.getuid()) + '/gvfs/'
        self._gvfsMountpointsDirExists = os.path.isdir(self._gvfsMountpointsDir)
        self._initializeCache()

# =============================================================================================

