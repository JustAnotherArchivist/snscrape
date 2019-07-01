# snscrape
snscrape is a scraper for social networking services (SNS). It scrapes things like user profiles, hashtags, or searches and returns the discovered items, e.g. the relevant posts.                  

The following services are currently supported:
* Facebook: user profiles and groups
* Gab: user profile posts, media, and comments
* Google+: user profiles
* Instagram: user profiles, hashtags, and locations
* Twitter: user profiles, hashtags, searches, threads, and lists (members as well as posts)
* VKontakte: user profiles

## Requirements
snscrape requires Python 3.6 or higher. The Python package dependencies are installed automatically when you install snscrape.

Note that one of the dependencies, lxml, also requires libxml2 and libxslt to be installed.

## Installation
    pip3 install snscrape

If you want to use the development version:

    pip3 install git+https://github.com/JustAnotherArchivist/snscrape.git

## Usage
To get all tweets by Jason Scott (@textfiles):

    snscrape twitter-user textfiles

It's usually useful to redirect the output to a file for further processing, e.g. in bash using the filename `@textfiles-tweets`:
```bash
snscrape twitter-user textfiles >twitter-@textfiles
```

To get the latest 100 tweets with the hashtag #archiveteam:

    snscrape --max-results 100 twitter-hashtag archiveteam

`snscrape --help` or `snscrape <module> --help` provides details on the available options. `snscrape --help` also lists all available modules.

It is also possible to use snscrape as a library in Python, but this is currently undocumented.

## Issue reporting
If you discover an issue with snscrape, please report it at <https://github.com/JustAnotherArchivist/snscrape/issues>. If possible please run snscrape with `-vv` and `--dump-locals` and include the log output as well as the dump files referenced in the log in the issue. Note that the files may contain sensitive information in some cases and could potentially be used to identify you (e.g. if the service includes your IP address in its response). If you prefer to arrange a file transfer privately, just mention that in the issue.

## License
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program.  If not, see <https://www.gnu.org/licenses/>.
