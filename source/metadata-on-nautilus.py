#!/usr/bin/python

# =============================================================================================

# In order to have this script working (if it is currently not),
# run 'install.sh --' (should come with this script)

# IF YOU WILL BE RUNNING THIS NOT ON UBUNTU...
# #1 Install Mutagen, pyexiv2, Kaa Metadata and pypdf (Python 2 modules)
# #2 Install python-nautilus via your package manager
# #3 Check where python-nautilus extension must be placed in your system
#    and place a copy of this python script there with execute permission

# =============================================================================================
 
import os
import urllib

from gi.repository import Nautilus, GObject, Gtk, GdkPixbuf
                                        # Nautilus stuff ^

import Image                            # for reading image
import pyexiv2                          # for reading EXIF metadata
import mutagen.aac                      # for reading ADTS/ADIF AAC (.aac)
import mutagen.aiff                     # for reading AIFF (.aif, .aiff, ...)
import mutagen.apev2                    # for reading APEv2 metadata
import mutagen.asf                      # for reading ASF (.wmv, .wma, ...)
import mutagen.flac                     # for reading FLAC
import mutagen.id3                      # for reading ID3 metadata
import mutagen.monkeysaudio             # for reading Monkey's Audio (.ape)
import mutagen.mp3                      # for reading MPEG (.mp2, .mp3, ...)
import mutagen.mp4                      # for reading MP4 (.mp4, .m4a, .m4b, ...)
import mutagen.musepack                 # for reading Musepack (.mpc, .mp+, ...)
import mutagen.oggflac                  # for reading Ogg FLAC
import mutagen.oggopus                  # for reading Ogg Opus
import mutagen.oggspeex                 # for reading Ogg Speex
import mutagen.oggvorbis                # for reading Ogg Vorbis
import mutagen.oggtheora                # for reading Ogg Theora
import mutagen.optimfrog                # for reading OptimFROG (.ofr, .ofs, ...)
import mutagen.trueaudio                # for reading TrueAudio (.tta)
import mutagen.wavpack                  # for reading WavPack (.wv)

try: from pyPdf import PdfFileReader    # for reading PDF
except: pass

import kaa.metadata                     # for reading some other formats

# =============================================================================================

def hhmmss(duration):
	return "%02i:%02i:%02i" % ((int(duration/3600)), (int(duration/60%60)), (int(duration%60)))

kbps = " kbps"
Hz = " Hz"
placeholder = "-"

# =============================================================================================

class ColumnExtension(GObject.GObject, Nautilus.ColumnProvider, Nautilus.InfoProvider):
	def __init__(self):
		pass

	def info_fetching_failure(self, src, filename):
		if src != "": src = src + " "
		print "\033[1mmetadata-on-nautilus\033[0m :: Could not fetch " + src + "information from '" + filename + "'\n"

	def metadata_fetching_failure(self, fmt, filename):
		if fmt != "" and fmt != "some": fmt = "expected " + fmt + " "
		elif fmt == "some": fmt = "some "
		else: fmt = "any "
		print "\033[1mmetadata-on-nautilus\033[0m :: Could not fetch " + fmt + "metadata from '" + filename + "'\n"

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_image_info(self, file, filename, filemime):
		try:
			metadata = pyexiv2.ImageMetadata(filename)
			metadata.read()
			try:
				buff1 = str(metadata['Exif.Photo.DateTimeOriginal'].raw_value)
				file.add_string_attribute('photodate', buff1[:10].replace(':', '-'))
				file.add_string_attribute('year', buff1[:4])
			except: pass
			try: file.add_string_attribute('exif_sw', str(metadata['Exif.Image.Software'].raw_value))
			except: pass
			try: file.add_string_attribute('exif_flash', str(metadata['Exif.Photo.Flash'].raw_value))
			except: pass
		except: 
			self.metadata_fetching_failure("EXIF", filename)
		try:
			imagefile = Image.open(filename)
			buff1 = str(imagefile.size[0])
			buff2 = str(imagefile.size[1])
			file.add_string_attribute('width', buff1)
			file.add_string_attribute('height', buff2)
			file.add_string_attribute('dimensions', buff1+'x'+buff2)
		except:
			self.info_fetching_failure("image", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_mp4_info(self, file, filename):
		try:
			audio = mutagen.mp4.MP4(filename)
			# Many try/except attemps, for that the audio variable may not have some items defined
			try: file.add_string_attribute('album', audio["\xa9alb"][0])
			except: pass
			try: file.add_string_attribute('artist', audio["\xa9ART"][0])
			except: pass
			try: file.add_string_attribute('genre', audio["\xa9gen"][0])
			except: pass
			try: file.add_string_attribute('title', audio["\xa9nam"][0])
			except: pass
			try: file.add_string_attribute('tracknumber', audio["trkn"])
			except: pass
			try: file.add_string_attribute('year', audio["\xa9day"][0])
			except: pass
		except:
			self.metadata_fetching_failure("MP4", filename)
		try:
			avfile = open(filename)
			info = mutagen.mp4.MP4Info(avfile)
			file.add_string_attribute('bitrate', str(info.bitrate/1000) + kbps)
			file.add_string_attribute('samplerate', str(info.sample_rate) + Hz)
			file.add_string_attribute('duration', hhmmss(info.length))
			avfile.close()
		except:
			try: avfile.close()
			except: pass
			self.info_fetching_failure("MP4 stream", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_ogg_info(self, file, filename, filemime):
		#TODO: overcome lack of support for those info by mutagen for opus, flac and theora
		mimedetail = filemime[8:-4]
		if mimedetail == 'opus': # audio/x-opus+ogg
			av = mutagen.oggopus.OggOpus(filename)
		elif filemime.startswith('v'): # video/ogg, video/x-theora+ogg
			av = mutagen.oggtheora.OggTheora(filename)
			try: file.add_string_attribute('bitrate', str(av.info.bitrate/1000) + kbps)
			except: pass
		else:
			if mimedetail == 'flac': av = mutagen.oggflac.OggFLAC(filename) # audio/x-flac+ogg
			else:
				if mimedetail == 'speex': av = mutagen.oggspeex.OggSpeex(filename) # audio/x-speex+ogg
				else: av = mutagen.oggvorbis.OggVorbis(filename) # audio/x-vorbis+ogg
				try: file.add_string_attribute('bitrate', str(av.info.bitrate/1000) + kbps)
				except: pass
			try: file.add_string_attribute('samplerate', str(av.info.sample_rate) + Hz)
			except: pass
		try: file.add_string_attribute('duration', hhmmss(av.info.length))
		except: pass
		try:
			# Many try/except attemps, for that the av variable may not have some items defined
			try: file.add_string_attribute('album', av['ALBUM'][0])
			except: pass
			try: file.add_string_attribute('artist', av['ARTIST'][0])
			except: pass
			try: file.add_string_attribute('genre', av['GENRE'][0])
			except: pass
			try: file.add_string_attribute('title', av['TITLE'][0])
			except: pass
			try: file.add_string_attribute('tracknumber', "%02i" % (int(av['TRACKNUMBER'][0].split('/', 1)[0])))
			except: pass
			try: file.add_string_attribute('year', av.tags['DATE'][0])
			except: pass
		except:
			self.metadata_fetching_failure("Ogg", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_asf_info(self, file, filename):
		try:
			av = ASF(filename)
			# Many try/except attemps, for that the av variable may not have some items defined
			try: file.add_string_attribute('album', av.tags.__getitem__('WM/AlbumTitle'))
			except: pass
			try: file.add_string_attribute('artist', str(av['g_wszWMAuthor']))
			except: pass
			try: file.add_string_attribute('genre', av['WM/Genre'][0])
			except: pass
			try: file.add_string_attribute('title', av['Title'][0])
			except: pass
			try: file.add_string_attribute('tracknumber', "%02i" % (int(av['WM/TrackNumber'][0])))
			except: pass
			try: file.add_string_attribute('year', av['Year'][0])
			except: pass
		except:
			self.metadata_fetching_failure("ASF", filename)
		try:
			avfile = open(filename)
			asfinfo = ASFInfo(avfile)
			file.add_string_attribute('bitrate', asfinfo.pprint())
			avfile.close()
		except:
			try: avfile.close()
			except: pass
			self.info_fetching_failure("ASF stream", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_media_info(self, file, filename, filemime):
		if filemime.endswith(("matroska", "flv", "mpeg", "wav")):
			try:
				self.fetched = True
				info=kaa.metadata.parse(filename)
				try: file.add_string_attribute('duration', hhmmss(info.length/3600))
				except: self.fetched = False
				try: file.add_string_attribute('dimensions', str(info.video[0].width) + 'x'+ str(info.video[0].height))
				except: self.fetched = False
				try: 
					bitrate = int(round(info.audio[0].bitrate/1000)) + int(round(info.video[0].bitrate/1000))
					file.add_string_attribute('bitrate', str(bitrate) + kbps)
				except: self.fetched = False
				try: file.add_string_attribute('samplerate', str(int(info.audio[0].samplerate)) + Hz)
				except: self.fetched = False
				try: file.add_string_attribute('title', info.title)
				except: self.fetched = False
				try: file.add_string_attribute('artist', info.artist)
				except: self.fetched = False
				try: file.add_string_attribute('genre', info.genre)
				except: self.fetched = False
				try: file.add_string_attribute('tracknumber', info.trackno)
				except: self.fetched = False
				try: file.add_string_attribute('year', info.userdate)
				except: self.fetched = False
				try: file.add_string_attribute('album', info.album)
				except: self.fetched = False
				if not self.fetched: self.metadata_fetching_failure("some", filename)
			except:
				self.metadata_fetching_failure("some", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def read_id3_tags(self, file, filename):
		# This must be called from inside a major try/except
		audio = mutagen.id3.ID3(filename)
		# Many try/except attemps, for that the audio variable may not have some items defined
		try: file.add_string_attribute('album', audio['TALB'][0])
		except: pass
		try: file.add_string_attribute('artist', audio['TPE1'][0])
		except: pass
		try: file.add_string_attribute('genre', audio['TCON'][0])
		except: pass
		try: file.add_string_attribute('title', audio['TIT2'][0])
		except: pass
		try: file.add_string_attribute('tracknumber', "%02i" % (int(audio['TRCK'][0].split('/', 1)[0])))
		except: pass
		try: file.add_string_attribute('year', audio['date'][0])
		except: pass

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def read_ape_tags(self, file, filename):
		# This must be called from inside a major try/except
		audio = mutagen.apev2.APEv2(filename)
		# Many try/except attemps, for that the audio variable may not have some items defined
		try: file.add_string_attribute('album', audio['Album'][0])
		except: pass
		try: file.add_string_attribute('artist', audio['Artist'][0])
		except: pass
		try: file.add_string_attribute('genre', audio['Genre'][0])
		except: pass
		try: file.add_string_attribute('title', audio['Title'][0])
		except: pass
		try: file.add_string_attribute('tracknumber', "%02i" % (int(audio['Track'][0].split('/', 1)[0])))
		except: pass
		try: file.add_string_attribute('year', audio['Year'][0])
		except: pass

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def read_flac_tags(self, file, filename):
		# This must be called from inside a major try/except
		audio = mutagen.flac.FLAC(filename)
		# Many try/except attemps, for that the audio variable may not have some items defined
		try: file.add_string_attribute('album', audio['ALBUM'][0])
		except: pass
		try: file.add_string_attribute('artist', audio['ARTIST'][0])
		except: pass
		try: file.add_string_attribute('genre', audio['GENRE'][0])
		except: pass
		try: file.add_string_attribute('title', audio['TITLE'][0])
		except: pass
		try: file.add_string_attribute('tracknumber', "%02i" % (int(audio['TRACKNUMBER'][0].split('/', 1)[0])))
		except: pass
		try: file.add_string_attribute('year', audio['DATE'][0])
		except: pass

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def read_ape_or_id3_tags(self, file, filename):
		try: read_ape_tags(file, filename)
		except: 
			try: read_id3_tags(file, filename)
			except: self.metadata_fetching_failure("", filename)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def fetch_audio_info(self, file, filename, filemime):
		avfile = open(filename)
		filesig = avfile.read(3)
		avfile.seek(os.stat(filename).st_size - 32)
		filetail = avfile.read(8)
		avfile.seek(0)

		# TODO: I'm Debugging some stuff in a very questionable and ugly way
		print "file##: " + filename[-4:] + " [" + filemime + "]"
		print "filesig: " + str(filesig) + "\nfiletail: " + str(filetail) + "\n"

		self.fetched = False
		if filesig == b'ID3': 
			try:
				read_id3_tags(file, filename)
				self.fetched = True
			except:
				self.metadata_fetching_failure("ID3v2", filename)
		elif filetail == b'APETAGEX': 
			try:
				read_ape_tags(file, filename)
				self.fetched = True
			except:
				self.metadata_fetching_failure("APE", filename)
		elif filesig == b'fLa': 
			try:
				read_flac_tags(file, filename)
				self.fetched = True
			except:
				self.metadata_fetching_failure("FLAC", filename)

		try:
			if filemime.endswith(('/mpeg', 'mp2')): # audio/mpeg, audio/x-mp2
				info = mutagen.mp3.MPEGInfo(avfile)
				file.add_string_attribute('bitrate', str(info.bitrate/1000) + kbps)
				if not self.fetched:
					try: read_id3_tags(file, filename)
					except: 
						try: 
							if filemime.endswith('g'): read_ape_tags(file, filename)
						except: self.metadata_fetching_failure("", filename)
			elif filemime.endswith('/aac'): # audio/aac
				info = mutagen.aac.AACInfo(avfile)
				file.add_string_attribute('bitrate', str(info.bitrate/1000) + kbps)
				if not self.fetched:
					try: read_id3_tags(file, filename)
					except: self.metadata_fetching_failure("", filename)
			elif filemime.endswith('musepack'): # audio/x-musepack
				info = mutagen.musepack.MusepackInfo(avfile)
				file.add_string_attribute('bitrate', str(info.bitrate/1000) + kbps)
				if not self.fetched: read_ape_or_id3_tags(file, filename)
			elif filemime[:-1].endswith('aif'): # audio/x-aiff, audio/x-aifc
				info = mutagen.aiff.AIFFInfo(avfile)
				file.add_string_attribute('bitrate', str(info.bitrate/1000) + kbps)
			elif filemime.endswith('flac'): # audio/flac
				info = mutagen.flac.StreamInfo(avfile)
				if not self.fetched:
					try: read_flac_tags(file, filename)
					except: 
						try: read_ape_tags(file, filename)
						except: self.metadata_fetching_failure("", filename)
			elif filemime.endswith('/x-ape'): # audio/x-ape
				info = mutagen.monkeysaudio.MonkeysAudioInfo(avfile)
				if not self.fetched:
					try: read_ape_tags(file, filename)
					except: self.metadata_fetching_failure("APE", filename)
			elif filemime.endswith('wavpack'): # audio/x-wavpack
				info = mutagen.wavpack.WavPackInfo(avfile)
				if not self.fetched: read_ape_or_id3_tags(file, filename)
			elif filemime.endswith('x-tta'): # audio/x-tta
				info = mutagen.trueaudio.TrueAudioInfo(avfile)
			elif filename.endswith(('.ofr', '.ofs')): # OptimFROG (no MIME)
				info = mutagen.optimfrog.OptimFROGInfo(avfile)
				if not self.fetched: read_ape_or_id3_tags(file, filename)
			else: 
				try: avfile.close()
				except: pass
				return
			file.add_string_attribute('samplerate', str(info.sample_rate) + Hz)
			file.add_string_attribute('duration', hhmmss(info.length))
		except:
			self.info_fetching_failure("", filename)

		avfile.close()

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def get_columns(self):
		return (
			Nautilus.Column(name='NautilusPython::album_col',       attribute='album',
				label="Album",           description="Song album"),
			Nautilus.Column(name='NautilusPython::artist_col',      attribute='artist',
				label="Artist",          description="Artist of the work"),
			Nautilus.Column(name='NautilusPython::bitrate_col',     attribute='bitrate',
				label="Bitrate",         description="Overall bitrate"),
			Nautilus.Column(name='NautilusPython::photodate_col',   attribute='photodate',
				label="Capture Date",    description="Photo capture date"),
			Nautilus.Column(name='NautilusPython::dimensions_col',  attribute='dimensions',
				label="Dimensions",      description="Actual pixel dimensions"),
			Nautilus.Column(name='NautilusPython::duration_col',    attribute='duration',
				label="Duration",        description="Audio or video duration"),
			Nautilus.Column(name='NautilusPython::genre_col',       attribute='genre',
				label="Genre",           description="Genre of the work"),
			Nautilus.Column(name='NautilusPython::height_col',      attribute='height',
				label="Height",          description="Actual pixel height"),
			Nautilus.Column(name='NautilusPython::samplerate_col',  attribute='samplerate',
				label="Sample Rate",     description="Audio sample rate"),
			Nautilus.Column(name='NautilusPython::title_col',       attribute='title',
				label="Title",           description="Title of the work"),
			Nautilus.Column(name='NautilusPython::tracknumber_col', attribute='tracknumber',
				label="Track #",         description="Track number"),
			Nautilus.Column(name='NautilusPython::width_col',       attribute='width',
				label="Width",           description="Actual pixel width"),
			Nautilus.Column(name='NautilusPython::year_col',        attribute='year',
				label="Year",            description="The year of creation of a work"),
			Nautilus.Column(name='NautilusPython::exif_sw_col',     attribute='exif_sw',
				label="Software (EXIF)", description="Software used to save the image (EXIF)"),
			Nautilus.Column(name='NautilusPython::exif_flash_col',  attribute='exif_flash',
				label="Flash (EXIF)",    description="Flash mode (EXIF)"),
		)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =

	def update_file_info(self, file):
		if placeholder != "":
			file.add_string_attribute('album', placeholder)
			file.add_string_attribute('artist', placeholder)
			file.add_string_attribute('bitrate', placeholder)
			file.add_string_attribute('photodate', placeholder)
			file.add_string_attribute('dimensions', placeholder)
			file.add_string_attribute('duration', placeholder)
			file.add_string_attribute('genre', placeholder)
			file.add_string_attribute('height', placeholder)
			file.add_string_attribute('samplerate', placeholder)
			file.add_string_attribute('title', placeholder)
			file.add_string_attribute('tracknumber', placeholder)
			file.add_string_attribute('width', placeholder)
			file.add_string_attribute('year', placeholder)
			file.add_string_attribute('exif_sw', placeholder)
			file.add_string_attribute('exif_flash', placeholder)

		if file.get_uri_scheme() != 'file':
			return

		# strip file:// to get absolute path
		filename = urllib.unquote(file.get_uri()[7:])
		# get the file's MIME type, to determine what to do
		filemime = file.get_mime_type()
		
		if filemime.startswith('image/'): 
			if filemime.endswith(('/jpeg', '/png', '/gif', '/bmp', '/tiff')):
				self.fetch_image_info(file, filename, filemime)
		elif filemime.startswith(('audio/', 'video/')) or filename.endswith(('.ofr', '.ofs')):
			if filemime.endswith(('mp4', 'm4b')): 
				self.fetch_mp4_info(file, filename)
			elif filemime.endswith('ogg'): 
				self.fetch_ogg_info(file, filename, filemime)
			elif filemime.endswith(('wma', 'wmv', 'msvideo')):
				self.fetch_asf_info(file, filename)
			elif filemime.startswith('v') or filemime.endswith('wav'):
				self.fetch_media_info(file, filename, filemime)
			else:
				self.fetch_audio_info(file, filename, filemime)
		elif filemime == 'application/pdf': 
			try:
				f = open(filename, 'rb')
				pdf = PdfFileReader(f)
				try: file.add_string_attribute('title', pdf.getDocumentInfo().title)
				except: pass
				try: file.add_string_attribute('artist', pdf.getDocumentInfo().author)
				except: pass
				f.close()
			except:
				pass # No metadata
					
		self.get_columns()

# =============================================================================================

