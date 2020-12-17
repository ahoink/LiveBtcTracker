# LiveBtcTracker
Live Bitcoin chart averaging data from multiple exchanges

It's still in Beta for now, but it works

Can also track altcoins such as Ethereum (ETH) BitcoinCash (BCH) and many more.

## Usage
`python LiveBtcTracker.py [options]` (use --help for info on options)

## Requirements/Dependencies
Dependencies must be manual installed at the moment. 
* Python 3.x
* matplotlib (2.0.2 or higher)
* requests

## About
This project uses data from multiple exchanges and matplotlib to chart Bitcoin in real-time. This includes a typical candlestick chart, volume bar chart, and technical indicators. The plot is configurable to different timeframes and interval sizes (although each exchange API can only work with specific time intervals).

Data is currently sourced from the following exchanges:
* Binance
* OKEx
* Coinbase Pro
* Bitfinex
* Gemini

All price information (open, high, low, close) is averaged between all data sources.

Volume information is the sum of all exchanges. Buy volume percentages are based only on Binance as they are they only exchange whose API provides this information. Volume bars are colored based on the percentage of buys during that interval, NOT the price action. (i.e. green bars mean more buys than sells)

### Technical Indicators
* MACD
* RSI
* OBV
* Fibonacci Retracement (Toggle with the 'R' key)
* Bollinger Bands (Toggle with the 'B' key)

## Example
![Example Image of Chart](chartexample.png)

## Future Work
I plan to update this as it fits my wants and needs. If you have different ideas or desires feel free to fork it. However, you may also make suggestions and requests.

I plan do eventually add the following (no specific order)
* Various additional indicators, price bands, etc.
* Ability to configure indicators at runtime
* Ability to change time interval at runtime
* More accurate time intervals (timezones messes this up right now)
* Make GUI display consistently between platforms (Windows, Linux, MacOS)
* pip install (application will no longer be considered beta phase at this point, v0.x -> v1.x)

Also, it turns out matplotlib isn't great for real-time plotting. At some point I may decided to switch to a different library.

## Donations/Tips
appreciated but not required :)

BTC:  1Kbq4egRfRCioRWGkFgZkJAxuzCQxqsEoU