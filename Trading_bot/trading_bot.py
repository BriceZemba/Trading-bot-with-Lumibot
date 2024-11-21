from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting # Pour le BackTest
from lumibot.strategies.strategy import Strategy
from datetime import datetime
from timedelta import Timedelta
from dotenv import load_dotenv
from lumibot.traders import Trader
import os
from alpaca_trade_api import REST
from finbert_utils import estimate_sentiment

load_dotenv()

# Paramètres de backtesting
start_day = datetime(2020, 1, 1)
end_day = datetime(2020, 12, 31)

# Charger les informations d'authentification d'Alpaca depuis .env
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = "https://api.alpaca.markets"

# Configuration d'Alpaca
ALPACA_CREDS = {
    "API_KEY": API_KEY,
    "API_SECRET": API_SECRET,
    "PAPER": False
}

broker = Alpaca(ALPACA_CREDS)

class MLTrader(Strategy):
    def initialize(self, symbol: str = 'SPY'): # Initialisation
        super().initialize()
        self.symbol = symbol
        self.sleeptime = "24H"
        self.last_trade = None
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key= API_SECRET)

    def position_sizing(self, cash_at_risk:float = .5):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * cash_at_risk / last_price, 0)
        return cash, last_price, quantity
    
    def get_dates(self):
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days = 3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')
    
    def get_sentiment(self):
        # Récupérer les informations de news et les sentiments
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, 
                                 start=three_days_prior,
                                 end= today)
        news = [ev.__dict__["_raw"]['headline'] for ev in news]
        probality, sentiment = estimate_sentiment(news)
        return probality, sentiment

    def on_trading_iteration(self): # Trading logic here
        cash, last_price, quantity = self.position_sizing()
        probality, sentiment = self.get_sentiment()
        if cash > last_price :
                if sentiment == "positive" and probality > .999:
                    if self.last_trade == "sell":
                         self.sell_all()
                
                order = self.create_order( # Create an order for the bot
                    self.symbol,
                    quantity,
                    'buy',
                    type='bracket',
                    take_profit_price= last_price * 1.20,
                    stop_loss_price= last_price * 0.95
                )
                self.submit_order(order) # Excecuter l'ordre crée
                self.last_trade = 'buy' 
        
        elif sentiment == "negative" and probality > .999:
                if self.last_order == "buy":
                    self.sell_all()
                
                order = self.create_order(
                    self.symbol,
                    quantity,
                    'sell',
                    type='bracket',
                    take_profit_price= last_price * .8,
                    stop_loss_price= last_price * 1.05
                )
                self.submit_order(order) # Soumettre l'ordre
                self.last_trade = 'sell'
        

# Initialisation et backtest de la stratégie
strategy = MLTrader(name='mlstrat', broker=broker, parameters={"symbol": 'SPY', "cash_at_risk":.5})

strategy.backtest(
    YahooDataBacktesting, 
    start_day,
    end_day,
    parameters={"symbol": 'AAPL', "cash_at_risk":.5}
)

# trader = Trader()
# trader.add_strategy(strategy)
# trader.run_all()