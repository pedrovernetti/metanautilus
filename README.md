# Metanautilus

Metanautilus is a python extension for [Nautilus](https://en.wikipedia.org/wiki/GNOME_Files) (GNOME File Manager, usually shipped with Debian, Fedora, openSUSE and Ubuntu) which makes many details (metadata) from files visible on list view.

### Characteristics

* __All__ and every metadata fetched from __local__ files is __cached__, so that from the second time you open the same folder onwards, there will be no overhead to display the information;
* __Any changes__ made to any file are __automatically considered__, since each cache entry is stored together with the time of its last modification (_st_mtime_);
* Files smaller than __16B__ are automatically __ignored__ to save time;
* Files in [__Samba__](https://en.wikipedia.org/wiki/Samba_(software)) shares and [__MTP__](https://en.wikipedia.org/wiki/Media_Transfer_Protocol) devices are __fully supported__, being the caching functionality unavailable for these, however;
* Only tries fetching any infomartion other than the Index Node from regular files and symbolic links, skipping special files to save time;
* Non-local files bigger than 256MB have only their Index Node fetched, too;
* The cached information is periodically stored in two separate files at `~/.cache/metanautilus/` by a daemon thread: `known-junk` (list of known ignorable files) and `known-metadata` (already fetched metadata).

### Details/Metadata Currently Supported

* __Album__
* __Artist__ *[same as Performer, Track Artist]*
* __Author__ *[audio's Composer (preferred), Lyricist, Writer; video's Director (preferred); ...]*
* __Bitrate__ *[Overall Bitrate, for multitrack files] [kbps]*
* __Camera Model__
* __Comment__ *[same as Description, Information]*
* __Date__ *[images' Capture Date, audio/video Release Date, documents' Creation Date, ...] [YYYY-MM-DD]*
* __Dimensions__ *[WxH]*
* __Duration__ *[HH:MM:SS]*
* __Genre__ *[Category, for some files]*
* __Height__
* __Index Node__ *[file system's inode number]*
* __Pages__ *[documents' Page Count, images' Layer Count]*
* __Sample Rate__ *[audio track's Sample Rate] [Hz]*
* __Title__ *[same as Name, Product Name]*
* __#__ *[Track Number, Episode Number, ...] [zero-padded - like '01' - without total tracks/episodes]*
* __Width__
* __Year__ *[the 'YYYY' from Date]*

### Supported Formats

* __Documents__: 
  * File Formats: _HTML_ (.htm, .html, .xhtml); _PDF_ (.pdf);
* __Images__:
  * File Formats: 
  * Format-Agnostic Metadata: 
* __Media__: 
  * File Formats: __MP3__ (.mp3); __Matroska__ (.mka, .mkv, mk3d); __MP4__ (.mp4, .m4a, .m4b, .m4p, .m4v); __FLAC__ (.flac); __WebM__ (.webm); __Ogg__ (.ogg, .oga, .ogv); __ASF__ (.asf, .wma, .wmv); __Monkey’s Audio__ (.ape); __WavPack__ (.wv); __Musepack__ (.mpc, .mpp, .mp+); __AC3__ (.ac3); __3GPP__ (.3gp, .3g2, .3gp2, .3gpp, .3p2); __MP2__ (.mp2);
  * Format-Agnostic Metadata: __ID3__, __APEv2__
* __Other__:
  * File Formats: __Torrent__ (.torrent);

