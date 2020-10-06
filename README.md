# Tweet2Cash
 Buy and sell stocks based on tweets using lemon.markets

## Table of contents
* [General info](#general-info)
* [Technologies](#technologies)
* [Setup](#setup)
* [Config](#config)

## General info
Trade stocks based on the sentiments of people's tweets!
Currently, Lemon offeres $10k in "Trial Money," so I encourage everyone to test out this script
This is incredibly unreliable and not recommended if you're actually looking to make money. [Send me an email](mailto:contact@leibmann.org) or fork the project if you find better configuration options
	
## Technologies
Project is created with:
* [Tweepy](https://pypi.org/project/tweepy/): 3.9
* [NLTK](https://www.nltk.org/): 3.5
* [My implementation](https://github.com/Pop101/Lemon) of [Lemon.markets](lemon.markets)' api
	
## Setup
To run this project, simply download it and install the requirements with `pip3 install -r requirements.txt`.
Then, specify your api-keys for both lemon.markets and twitter in `./config.yml`
Now, just run it with python3!
<b>Running in a screen or as a backround process is recommended</b>

## Config
If you recieve `Error in Config`, make sure you have all the required fields. Alternatively, you can redownload the default config.
```yml

# Keys
twitter:
  consumer-key: <KEY>
  consumer-secret: <SECRET>
  app-token: <TOKEN>
  app-secret: <SECRET>
lemon: <KEY>
lemon-account-name: Demo

#---Config---#
verbose: true

# how closely company names and tweet text need to match. Anything below 1.4 is fine.
match-factor: 0.8

# If set to true, the match factor will depend on the length of the stock's name. A value of 4-6 is fine for this
match-weigthed: false

# the maximum amount of Euros to spend on a single transaction
transaction-limit: 50

# How many seconds before market close it should release all its "profit orders."
# Keep it high to avoid losing money to post-market movement
limit-time: 3600

# If set to true, will sell all of the selected stock instead of a limited number
sell-all-mode: true

# the user IDS to follow and trust
user-ids:
  # "political" figures
  - 25073877 # trump
  - 1339835893 # hillary clinton
  - 409486555 # michelle obama
  - 813286 # barak obama
  - 30354991 # kamala harris
  - 939091 # joe biden
  # influencial figures
  - 961445378 # mcaffee
  - 50393960 # bill gates
  # news sources
  - 14677919 # new yorker
  # stock news
  - 1089978712685273090 # stock_market_pr
  - 786038665625555000 # stocktiprobot
```
