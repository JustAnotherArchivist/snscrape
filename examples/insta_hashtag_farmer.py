import snscrape.base
import snscrape.modules
import snscrape.version

import sqlite3
import urllib.request
import os.path
import time
import sys

from datetime import date, datetime
from urllib.parse import urlparse

def main():
    if len(sys.argv) != 2:
        print("Usage {} <hashtag>".format(sys.argv[0]))
        sys.exit(2)
    
    # The tag we want to scrape 
    tag = str(sys.argv[1])

    # Setup scraper variables
    limit = 150000
    scraper = snscrape.modules.instagram.InstagramHashtagScraper(
        name=tag, mode='Hashtag')

    # Setup Database to hold out posts data
    db = sqlite3.connect('data.db')
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS igPosts(id TEXT PRIMARY KEY, cleanUrl TEXT, dirtyUrl TEXT, 
            content TEXT, thumbnailUrl TEXT, displayUrl TEXT, username TEXT, 
            commentsDisabled NUMERIC, isVideo NUMERIC, date INTEGER, likes INTEGER, comments INTEGER)
    ''')
    db.commit()
	
    print("Getting tag", tag)
    # Snscrape will loop through more posts until you break so you have to deal with counting yourself
    for i, item in enumerate(scraper.get_items(), start=1):
        addItemToDB(db,item)
        if i == limit:
            break

    db.close()


def addItemToDB(db,item):
    try:
        cursor = db.cursor()

        #Generate unique key from the id of the image
        a = os.path.normpath(item.cleanUrl)
        id = os.path.basename(a)

        cursor.execute('''INSERT OR REPLACE INTO igPosts(
            id,cleanUrl,dirtyUrl,content,thumbnailUrl,displayUrl,username,commentsDisabled,isVideo,date,likes,comments)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (
                        id,
                        item.cleanUrl,
                        item.dirtyUrl,
                        item.content,
                        item.thumbnailUrl,
                        item.displayUrl,
                        item.username,
                        item.commentsDisabled,
                        item.isVideo,
                        item.date,
                        item.likes,
                        item.comments
                    )
                )

        db.commit()
    except Exception as e:
        print("Failed with:")
        print(e)
        

if __name__ == '__main__':
    main()