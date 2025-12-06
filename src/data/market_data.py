# Updated PE Ratio Retrieval

import logging
import yfinance as yf

# Setup logging
logging.basicConfig(level=logging.INFO)

class MarketData:
    def __init__(self, ticker):
        self.ticker = ticker

    def get_pe_ratio(self):
        try:
            stock = yf.Ticker(self.ticker)
            # Use new method to get PE ratio
            pe_ratio = stock.info['forwardPE'] if 'forwardPE' in stock.info else stock.info['trailingPE']
            logging.info(f"Retrieved PE ratio: {pe_ratio}")
            return pe_ratio
        except KeyError as e:
            logging.error(f"KeyError: {e}, could not retrieve PE ratio, falling back to defaults.")
            return None  # Add fallback logic as needed
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return None  # Add fallback logic as needed
