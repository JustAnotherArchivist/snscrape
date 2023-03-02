import snscrape.modules.twitter as twitterScraper

scrapper = twitterScraper.TwitterUserScraper("rfloyd7") # userid

twitterScraper.Twitt

tweets = []

for i,tweet in enumerate(scrapper.get_items()):
    if i>1:
        break
    # tweets.append({
    #     "id":tweet.id,
    #     "content":tweet.rawContent,
    #     "date": tweet.displayname
    # })
    print(tweet)
    print(tweet.username)
    print(tweet.user.displayname)
    

# print(tweets)

