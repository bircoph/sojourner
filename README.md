**Sojourner** is a conference schedule viewer for the [Nokia N900](http://maemo.nokia.com/n900/), the smartphone of choice for the discerning sandal-wearer. Talks can be viewed by topic, by room or by time; your favourite events can be starred for easy browsing later on.

It originally showed the schedule for [FOSDEM](http://fosdem.org/); it has subsequently been made to show others, thanks mainly to wonderful contributors! It's written in *Python* and uses the [Hildon](http://pymaemo.garage.maemo.org/python_hildon_manual/) widget set. 

This software was created by [Will Thompson](http://willthompson.co.uk/) and he deserves all the credit; I just fix critical bugs and make new releases. This is the official and actively maintained fork.

Download
--------
This app can be downloaded directly from extras-devel or extras-testing [Maemo repository](http://maemo.org/packages/view/sojourner/). Alternatively binary debian package can be downloaded from [Releases page](https://github.com/loomchild/sojourner/releases).

Packaging
---------
To build sojourner debian package you need N900 SDK. The easiest (but probably not the fastest) way to obtain it is to use vagrant. Configuration file can be downloaded from here: https://github.com/silvio/vagrant-n900-sdk

After booting the virtual machine run scratchbox

	scratchbox

Install the package dependencies (only first time)
	
	fakeroot apt-get install cdbs python2.5 python-central

Go to the project directory and build the package (share files between host system and scratchbox via /tmp directory)
	
	dpkg-buildpackage -rfakeroot

More info about these commands can be found [here](http://wiki.maemo.org/Documentation/Maemo_5_Developer_Guide/Packaging,_Deploying_and_Distributing).

Uploading
---------
The package upload process is described [here](http://wiki.maemo.org/Uploading_to_Extras-devel).

I use [extras assistant](https://garage.maemo.org/extras-assistant/index.php). After uploading the package will be available in extras-devel repo and on [package website](http://maemo.org/packages/view/sojourner/) within few hours. Do not try to upload twice, because the hash will not match. After image is tested it can be promoted by chosing desired version and clicking Promote.

Adding a conference
-------------------

Things to remember:

* update banner (see [icons/](icons/) for input file)
* rename conference file, update links in setup
* update version in __init__ file and changelog
* see [this commit](https://github.com/loomchild/sojourner/commit/c58164a91d1c9bb354dcb4f094d425cbfd53b96a) for reference
