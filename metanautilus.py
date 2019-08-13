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
 
import sys, os, stat, urllib               # basics
import pickle

import threading

print("Initializing metadata-on-nautilus [Python " + sys.version.partition(' (')[0] + "]")

from gi import require_version       # Nautilus stuff
require_version("Gtk", "3.0")        # 
require_version('Nautilus', '3.0')   # ...
from gi.repository import Nautilus, GObject, Gtk, GdkPixbuf

import lxml.html                     # for reading XML/HTML

from PIL import Image                # for reading image
import pyexiv2                       # for reading EXIF metadata

import mutagen.aac                   # for reading ADTS/ADIF AAC (.aac)
import mutagen.aiff                  # for reading AIFF (.aif, .aiff, ...)
import mutagen.apev2                 # for reading APEv2 metadata
import mutagen.asf                   # for reading ASF (.wmv, .wma, ...)
import mutagen.flac                  # for reading FLAC
import mutagen.id3                   # for reading ID3 metadata
import mutagen.monkeysaudio          # for reading Monkey's Audio (.ape)
import mutagen.mp3                   # for reading MPEG (.mp2, .mp3, ...)
import mutagen.mp4                   # for reading MP4 (.mp4, .m4a, .m4b, ...)
import mutagen.musepack              # for reading Musepack (.mpc, .mp+, ...)
import mutagen.oggflac               # for reading Ogg FLAC
import mutagen.oggopus               # for reading Ogg Opus
import mutagen.oggspeex              # for reading Ogg Speex
import mutagen.oggvorbis             # for reading Ogg Vorbis
import mutagen.oggtheora             # for reading Ogg Theora
import mutagen.optimfrog             # for reading OptimFROG (.ofr, .ofs, ...)
import mutagen.trueaudio             # for reading TrueAudio (.tta)
import mutagen.wavpack               # for reading WavPack (.wv)
from enzyme import MKV              
from pymediainfo import MediaInfo

from PyPDF2 import PdfFileReader     # for reading PDF
from ebooklib import epub            # for reading EPUB

from torrentool.api import Torrent

# =============================================================================================

kbps = " kbps"
Hz = " Hz"
placeholder = "-"

# =============================================================================================

class fileMetadata():
    def __init__(self):
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

# =============================================================================================

class ColumnExtension(GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider):

    cacheFile = os.getenv("HOME") + '/.cache/metadata-on-nautilus/known-metadata'

    def __init__(self):
        if os.path.exists(self.cacheFile) and os.path.isfile(self.cacheFile):
            with open(self.cacheFile, 'rb') as cacheHandle:
                self.knownFiles = pickle.load(cacheHandle)
        else:
            self.knownFiles = dict()
        
    def __del__(self):
        if not os.path.exists(self.cacheFile) or os.path.isfile(self.cacheFile):
            with open(self.cacheFile, 'wb') as cacheHandle:
                pickle.dump(self.knownFiles, cacheHandle, protocol=pickle.HIGHEST_PROTOCOL)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _formatedDuration(self, secs):
        return "%02i:%02i:%02i" % ((int(secs/3600)), (int(secs/60%60)), (int(secs%60)))
        
    def _formatedTrackNumber(self, tracknumberstring):
        pos = 0
        for c in tracknumberstring:
            if (c > '9') or (c < '0'): break
            pos += 1
        if pos == 0: return placeholder
        elif pos == 1: return '0' + tracknumberstring[0]
        return tracknumberstring[:pos]
        
    def _formatedBitrate(self, bitratestring):
        finalstring = ''
        for c in bitratestring:
            if (c > '9') or (c < '0'): finalstring += c
        return (finalstring + kbps)
        
    def _formatedDate(self, datestring):
        size = len(datestring)
        if (size >= 10): return datestring[:10]
        elif (size == 4): return datestring + '-??-??'
        elif (size == 7): return datestring + '-??'
        else: return placeholder

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    
    def _fetchTorrentMetadata(self, metadata, path):
        try: torrent = Torrent.from_file(path)
        except: return
        if torrent.created_by is not None: metadata.author = torrent.created_by
        if torrent.creation_date is not None: 
            metadata.date = torrent.creation_date.isoformat()[:10]
            metadata.year = metadata.date[:4]
        if torrent.comment is not None: metadata.comment = torrent.comment
        if torrent.name is not None: metadata.title = torrent.name
    
    def _fetchXMLMetadata(self, metadata, path, mime):
        try: xml = lxml.html.parse(path)
        except: return
        title = xml.find(".//title")
        if title is None: title = xml.find(".//name")
        if title is not None: metadata.title = title.text
        
    def get_pdf_info(self, metadata, path):
        with open(path, 'rb') as documentfile:
            try: 
                document = PdfFileReader(documentfile)
                try: metadata.pages = str(document.getNumPages())
                except: pass
                try: 
                    info = document.getDocumentInfo()
                    metadata.author = info['/Author']
                    metadata.title = info['/Title']
                except:
                    pass
            except:
                pass

    def get_epub_info(self, metadata, path):
        try: document = epub.read_epub(path)
        except Exception as e: print(e)
        print("EPUB: " + path)
        print(document)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readOgg(self, metadata, path, mime):
        #TODO: overcome lack of support for those info by mutagen for opus, flac and theora
        mimedetail = mime[8:-4]
        if mimedetail == 'opus': # audio/x-opus+ogg
            av = mutagen.oggopus.OggOpus(path)
        elif mime.startswith('v'): # video/ogg, video/x-theora+ogg
            av = mutagen.oggtheora.OggTheora(path)
            try: metadata.bitrate = str(av.info.bitrate/1000) + kbps
            except: pass
        else:
            if mimedetail == 'flac': av = mutagen.oggflac.OggFLAC(path) # audio/x-flac+ogg
            else:
                if mimedetail == 'speex': av = mutagen.oggspeex.OggSpeex(path) # audio/x-speex+ogg
                else: av = mutagen.oggvorbis.OggVorbis(path) # audio/x-vorbis+ogg
                try: metadata.bitrate = str(av.info.bitrate/1000) + kbps
                except: pass
            try: metadata.samplerate = str(av.info.sample_rate) + Hz
            except: pass
        try: metadata.duration = self._formatedDuration(av.info.length)
        except: pass
        try:
            metadata.album = av.get('ALBUM', [placeholder])[0]
            metadata.artist = av.get('ARTIST', [placeholder])[0]
            metadata.genre = av.get('GENRE', [placeholder])[0]
            metadata.title = av.get('TITLE', [placeholder])[0]
            metadata.tracknumber = self._formatedTrackNumber(av.get('TRACKNUMBER', [placeholder])[0])
            metadata.year = av.get('DATE', [placeholder])[0]
        except:
            self.info_fetching_failure("Ogg", path)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readASF(self, metadata, file):
        try: av = mutagen.asf.ASF(file)
        except: return
        print("ASF YEAH")
        print(av)
        try: metadata.album = av.tags.__getitem__('WM/AlbumTitle')
        except: pass
        try: metadata.artist = av['g_wszWMAuthor'][0]
        except Exception as e: print("problema com Artist: " + str(e))
        print(av['WM/Genre'][0])
        try: metadata.genre = av['WM/Genre'].__str__()
        except: pass
        try: metadata.title = av['Title'][0]
        except: pass
        try: metadata.tracknumber = self._formatedTrackNumber(av['WM/TrackNumber'][0])
        except: pass
        try: metadata.year = av['Year'][0]
        except: pass
        try: metadata.bitrate = str(av.info.bitrate/1000) + kbps
        except: pass
        try: metadata.samplerate = str(av.info.sample_rate) + Hz
        except: pass
        try: metadata.duration = self._formatedDuration(av.info.length)
        except: pass

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readID3(self, metadata, file):
        try: audio = mutagen.id3.ID3(file)
        except: return
        metadata.album = audio.get('TALB', [placeholder])[0]
        metadata.artist = audio.get('TPE1', [placeholder])[0]
        composer = audio.get('TCOM')
        if composer is None: composer = audio.get('TEXT')
        if composer is not None: metadata.author = composer[0]
        metadata.genre = audio.get('TCON', [placeholder])[0]
        metadata.title = audio.get('TIT2', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRCK', [placeholder])[0])
        date = audio.get('TDRC')
        if date is not None: date = date[0].get_text()[:10]
        else: date = audio.get('TYER', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readMP4(self, metadata, file):
        try: av = mutagen.mp4.MP4(file)
        except: return    
        metadata.album = av.get('\xA9alb', [placeholder])[0]
        metadata.artist = av.get('\xA9ART', [placeholder])[0]
        metadata.author = av.get('\xA9wrt', [placeholder])[0]
        metadata.bitrate = str(av.info.bitrate / 1000) + kbps
        metadata.date = self._formatedDate(av.get('\xA9day', [placeholder])[0])
        metadata.duration = self._formatedDuration(av.info.length)
        metadata.genre = av.get('\xA9gen', [placeholder])[0]
        metadata.samplerate = str(av.info.sample_rate) + Hz
        metadata.title = av.get('\xA9nam', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(str(av.get('trkn', [[None]])[0][0]))
        metadata.year = av.get('\xA9day', [placeholder])[0][:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readFLAC(self, metadata, fileObject):
        try: audio = mutagen.flac.FLAC(fileObject)
        except: return
        metadata.album = audio.get('ALBUM', [placeholder])[0]
        metadata.artist = audio.get('ARTIST', [placeholder])[0]
        composer = audio.get('COMPOSER')
        if composer is None: 
            composer = audio.get('LYRICIST')
            if composer is None: composer = audio.get('WRITER')
        if composer is not None: metadata.author = composer[0]
        metadata.bitrate = str(audio.info.bitrate / 1000) + kbps
        metadata.duration = self._formatedDuration(audio.info.length)
        metadata.genre = audio.get('GENRE', [placeholder])[0]
        metadata.samplerate = str(audio.info.sample_rate) + Hz
        metadata.title = audio.get('TITLE', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('TRACKNUMBER', [placeholder])[0])
        date = audio.get('DATE', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readAPE(self, metadata, file):
        try: audio = mutagen.apev2.APEv2(file)
        except: return
        metadata.album = audio.get('Album', [placeholder])[0]
        metadata.artist = audio.get('Artist', [placeholder])[0]
        composer = audio.get('Composer')
        if composer is None: 
            composer = audio.get('Lyricist')
            if composer is None: composer = audio.get('Writer')
        if composer is not None: metadata.author = composer[0]
        metadata.genre = audio.get('Genre', [placeholder])[0]
        metadata.title = audio.get('Title', [placeholder])[0]
        metadata.tracknumber = self._formatedTrackNumber(audio.get('Track', [placeholder])[0])
        date = audio.get('Year', [placeholder])[0][:10]
        metadata.date = self._formatedDate(date)
        metadata.year = date[:4]

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _readUnknownAVFormat(self, metadata, path, basicInformationOnly = False):
        try: av = MediaInfo.parse(path)
        except: return
        if av.tracks[0].overall_bit_rate is not None: 
            metadata.bitrate = str(int(av.tracks[0].overall_bit_rate / 1000)) + kbps
        if av.tracks[0].other_duration is not None: 
            metadata.duration = av.tracks[0].other_duration[3][:8]
        elif av.tracks[0].duration is not None: 
            metadata.duration = self._formatedDuration(av.tracks[0].duration)
        for track in av.tracks:
            if track.track_type[0] == 'V':
                if track.width is not None: metadata.width = str(track.width)
                if track.height is not None: metadata.height = str(track.height)
            elif track.track_type[0] == 'A':
                if track.sampling_rate is not None: metadata.samplerate = str(track.sampling_rate) + Hz
            elif track.track_type[0] != 'G': break
        if basicInformationOnly: return
        if av.tracks[0].album is not None: metadata.album = av.tracks[0].album
        if av.tracks[0].director is not None: metadata.author = av.tracks[0].director
        if av.tracks[0].performer is not None: metadata.artist = av.tracks[0].performer
        if av.tracks[0].movie_name is not None: metadata.title = av.tracks[0].title
        elif av.tracks[0].track_name is not None: metadata.title = av.tracks[0].track_name
        elif av.tracks[0].title is not None: metadata.title = av.tracks[0].title
        if av.tracks[0].track_name_position is not None: metadata.tracknumber = av.tracks[0].track_name_position
        

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchAVMetadata(self, metadata, path, mime):
        isVideo = mime[0] == 'v'
        with open(path, 'rb') as avfile:
            filesig = avfile.read(8)
            avfile.seek(os.stat(path).st_size - 32)
            filetail = avfile.read(8)
            avfile.seek(0)
            if filesig.startswith(b'ID3'): self._readID3(metadata, avfile)
            elif filetail == b'APETAGEX': self._readAPE(metadata, avfile)
            else:
                if filesig.endswith(b'ftyp') and not isVideo: self._readMP4(metadata, avfile)
                elif filesig.startswith(b'0&\xB2u'): self._readASF(metadata, avfile)
                elif filesig.startswith(b'fLa'): self._readFLAC(metadata, avfile)
                elif filesig.startswith(b'MP+'): self._readMusepack(metadata, avfile)
                else: self._readUnknownAVFormat(metadata, path)
                return
            #if mime.endswith(('/mpeg', 'mp2')): # audio/mpeg, audio/x-mp2
            #    info = mutagen.mp3.MPEGInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000) + kbps
            #elif mime.endswith('/aac'): # audio/aac
            #    info = mutagen.aac.AACInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000) + kbps
            #elif mime.endswith('musepack'): # audio/x-musepack
            #    info = mutagen.musepack.MusepackInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000) + kbps
            #elif mime.endswith('aiff'): # audio/x-aiff
            #    info = mutagen.aiff.AIFFInfo(avfile)
            #    metadata.bitrate = str(info.bitrate/1000) + kbps
            #elif mime.endswith('/x-ape'): # audio/x-ape
            #    info = mutagen.monkeysaudio.MonkeysAudioInfo(avfile)
            #elif mime.endswith('wavpack'): # audio/x-wavpack
            #    info = mutagen.wavpack.WavPackInfo(avfile)
            #elif mime.endswith('x-tta'): # audio/x-tta
            #    info = mutagen.trueaudio.TrueAudioInfo(avfile)
            #elif path.endswith(('.ofr', '.ofs')): # OptimFROG (no MIME)
            #    info = mutagen.optimfrog.OptimFROGInfo(avfile)
            #metadata.samplerate = str(info.sample_rate) + Hz
            #metadata.duration = self._formatedDuration(info.length)

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def _fetchImageMetadata(self, metadata, path, mime):
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

    def get_columns(self):
        return (
            Nautilus.Column(name='NautilusPython::inode_col',        attribute='inode',
                label="Index Node",         description="Index Node of the file"),
            Nautilus.Column(name='NautilusPython::album_col',        attribute='album',
                label="Album",              description="The album the work is part of"),
            Nautilus.Column(name='NautilusPython::artist_col',       attribute='artist',
                label="Artist",             description="Artist of the work"),
            Nautilus.Column(name='NautilusPython::author_col',       attribute='author',
                label="Author",             description="Author of the work"),
            Nautilus.Column(name='NautilusPython::bitrate_col',      attribute='bitrate',
                label="Bit Rate",           description="Overall bitrate"),
            Nautilus.Column(name='NautilusPython::camera_col',       attribute='camera',
                label="Camera Model",       description="Camera model used to take the picture"),
            Nautilus.Column(name='NautilusPython::comment_col',      attribute='comment',
                label="Comment",            description="Comment"),
            Nautilus.Column(name='NautilusPython::date_col',         attribute='date',
                label="Date",               description="Year, Month and Day"),
            Nautilus.Column(name='NautilusPython::dimensions_col',   attribute='dimensions',
                label="Dimensions",         description="Actual pixel dimensions"),
            Nautilus.Column(name='NautilusPython::duration_col',     attribute='duration',
                label="Duration",           description="Audio or video duration"),
            Nautilus.Column(name='NautilusPython::exif_flash_col',   attribute='exif_flash',
                label="Flash (EXIF)",       description="Flash mode (EXIF)"),
            Nautilus.Column(name='NautilusPython::genre_col',        attribute='genre',
                label="Genre",              description="Genre of the work"),
            Nautilus.Column(name='NautilusPython::height_col',       attribute='height',
                label="Height",             description="Actual pixel height"),
            Nautilus.Column(name='NautilusPython::pages_col',        attribute='pages',
                label="Pages",              description="Page count of the document"),
            Nautilus.Column(name='NautilusPython::samplerate_col',   attribute='samplerate',
                label="Sample Rate",        description="Audio sample rate"),
            Nautilus.Column(name='NautilusPython::title_col',        attribute='title',
                label="Title",              description="Title of the work"),
            Nautilus.Column(name='NautilusPython::tracknumber_col',  attribute='tracknumber',
                label="#",                  description="Track number"),
            Nautilus.Column(name='NautilusPython::width_col',        attribute='width',
                label="Width",              description="Actual pixel width"),
            Nautilus.Column(name='NautilusPython::year_col',         attribute='year',
                label="Year",               description="Year"),
        )

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

    def update_file_info(self, file):
        path = urllib.unquote(file.get_uri()[7:])        
        try: status = os.stat(path)
        except: return
        
        metadata = fileMetadata()        
        previousMetadata = self.knownFiles.get(status.st_ino)
        
        if (previousMetadata is not None) and (previousMetadata[0] >= status.st_mtime):
            print(path + " was known")
            metadata = previousMetadata[1]
        elif (status.st_size > 8): #and file.get_uri_scheme() == 'file': # Skip non-local files
            mime = file.get_mime_type()
            if mime.startswith('ima'):
                self._fetchImageMetadata(metadata, path, mime)
            elif mime.startswith(('aud', 'vid')) or path.endswith(('.ofr', '.ofs')):
                self._fetchAVMetadata(metadata, path, mime)
            elif mime.startswith('app'):
                #reader1 = threading.Thread(target=thread_function, args=(1,))
                mime = mime[12:]
                if mime.endswith('pdf'): self.get_pdf_info(metadata, path)
                elif mime.startswith('epub'): self.get_epub_info(metadata, path)
                elif mime.endswith('torrent'): self._fetchTorrentMetadata(metadata, path)
        
        file.add_string_attribute('inode', str(status.st_ino))
        file.add_string_attribute('album', metadata.album)
        file.add_string_attribute('artist', metadata.artist)
        file.add_string_attribute('author', metadata.author)
        file.add_string_attribute('bitrate', metadata.bitrate)
        file.add_string_attribute('camera', metadata.camera)
        file.add_string_attribute('comment', metadata.comment)
        file.add_string_attribute('date', metadata.date)
        if (metadata.width is not placeholder) and (metadata.height is not placeholder):
            file.add_string_attribute('dimensions', (metadata.width + 'x' + metadata.height))
        else:
            file.add_string_attribute('dimensions', placeholder)
        file.add_string_attribute('duration', metadata.duration)
        file.add_string_attribute('genre', metadata.genre)
        file.add_string_attribute('height', metadata.height)
        file.add_string_attribute('pages', metadata.pages)
        file.add_string_attribute('samplerate', metadata.samplerate)
        file.add_string_attribute('title', metadata.title)
        file.add_string_attribute('tracknumber', metadata.tracknumber)
        file.add_string_attribute('width', metadata.width)
        file.add_string_attribute('year', metadata.year)
        file.add_string_attribute('exif_flash', metadata.exif_flash)
                    
        self.get_columns()

# =============================================================================================

