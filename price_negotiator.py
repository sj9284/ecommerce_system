import random
import spacy
from transformers import pipeline

try:
    nlp = spacy.load('en_core_web_sm')
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
except Exception as e:
    print(f"Error loading models: {e}")
    exit(1)

class NegotiationState:
    INITIAL = 1
    OFFER_MADE = 2
    COUNTER_OFFER = 3
    FINAL_OFFER = 4
    DEAL_CLOSED = 5
    NEGOTIATION_ENDED = 6

class Product:
    def __init__(self, name, base_price, min_price):
        self.name = name
        self.base_price = base_price
        self.min_price = min_price
        self.stock = 10

class PriceNegotiatorBot:
    def __init__(self, product_name, base_price, username):
        self.current_product = Product(product_name, float(base_price), float(base_price) * 0.8)
        self.state = NegotiationState.INITIAL
        self.current_offer = 0.0
        self.bot_counter = 0.0
        self.negotiation_attempts = 0
        self.max_attempts = 3
        self.username = username
        self.history = []

    def process_input(self, user_input):
        if not user_input and self.state == NegotiationState.INITIAL:
            self.state = NegotiationState.OFFER_MADE
            return f"The {self.current_product.name} is priced at ${self.current_product.base_price:.2f}. Would you like to make an offer?"

        doc = nlp(user_input.lower())
        intents = ["make_offer", "accept", "reject", "inquire_product", "add_to_cart"]
        intent_result = classifier(user_input, intents)
        intent = intent_result['labels'][0]
        offer_price = self._extract_price(user_input)

        if self.state == NegotiationState.OFFER_MADE:
            if intent == "reject" or "no" in user_input.lower():
                self.state = NegotiationState.NEGOTIATION_ENDED
                return "Okay, let me know if you change your mind!"
            if offer_price is None:
                return "Please make a specific price offer (e.g., 'I offer $200')."
            self.current_offer = offer_price
            self.negotiation_attempts += 1
            self.history.append(f"User offered ${offer_price}")
            if offer_price >= self.current_product.base_price:
                self.state = NegotiationState.DEAL_CLOSED
                return self._close_deal(offer_price)
            if offer_price < self.current_product.min_price:
                self.bot_counter = self.current_product.base_price * 0.95
                self.state = NegotiationState.COUNTER_OFFER
                return f"Your offer of ${offer_price:.2f} is too low. I can offer it for ${self.bot_counter:.2f}. What do you think?"
            discount = random.uniform(0.05, 0.1)
            self.bot_counter = self.current_product.base_price * (1 - discount)
            self.state = NegotiationState.COUNTER_OFFER
            return f"${offer_price:.2f} is a good start. I can counter with ${self.bot_counter:.2f}. Does that work for you?"

        elif self.state == NegotiationState.COUNTER_OFFER:
            if intent == "accept" or "yes" in user_input.lower():
                self.state = NegotiationState.DEAL_CLOSED
                return self._close_deal(self.bot_counter)
            if intent == "reject" or "no" in user_input.lower():
                self.state = NegotiationState.FINAL_OFFER
                final_price = max(self.current_product.min_price, self.bot_counter * 0.98)
                self.bot_counter = final_price
                return f"Let's wrap this up. My final offer is ${final_price:.2f}. Take it or leave it!"
            if offer_price is None:
                return "Please respond with a new offer or say 'yes' to accept my counter."
            self.current_offer = offer_price
            self.negotiation_attempts += 1
            self.history.append(f"User countered with ${offer_price}")
            if self.negotiation_attempts >= self.max_attempts:
                self.state = NegotiationState.FINAL_OFFER
                final_price = max(self.current_product.min_price, self.bot_counter * 0.98)
                self.bot_counter = final_price
                return f"Let's wrap this up. My final offer is ${final_price:.2f}. Take it or leave it!"
            if offer_price >= self.bot_counter:
                self.state = NegotiationState.DEAL_CLOSED
                return self._close_deal(offer_price)
            self.bot_counter = max(self.current_product.min_price, self.bot_counter - (self.bot_counter - offer_price) * 0.5)
            return f"I can meet you closer at ${self.bot_counter:.2f}. How does that sound?"

        elif self.state == NegotiationState.FINAL_OFFER:
            if intent == "accept" or "yes" in user_input.lower():
                self.state = NegotiationState.DEAL_CLOSED
                return self._close_deal(self.bot_counter)
            self.state = NegotiationState.NEGOTIATION_ENDED
            return "That's my best offer. Let me know if you reconsider!"

        elif self.state == NegotiationState.DEAL_CLOSED:
            if intent == "add_to_cart" or "add" in user_input.lower():
                negotiated_price = self.bot_counter if self.bot_counter else self.current_offer
                return f"add_to_cart:${negotiated_price}"
            return "Deal is closed. Type 'add' to add to cart, or let me know how to proceed."

        elif self.state == NegotiationState.NEGOTIATION_ENDED:
            return "Negotiation has ended. Start a new one if you'd like!"

        return "I'm not sure how to proceed. Could you please clarify your request?"

    def _extract_price(self, text):
        words = text.split()
        for word in words:
            if '$' in word or any(c.isdigit() for c in word):
                try:
                    price = float(''.join(c for c in word if c.isdigit() or c == '.'))
                    return price
                except ValueError:
                    continue
        return None

    def _close_deal(self, price):
        if self.current_product.stock > 0:
            self.current_product.stock -= 1
            self.history.append(f"Deal closed at ${price}")
            self.bot_counter = price
            return f"Deal closed! You've negotiated the {self.current_product.name} for ${price:.2f}. Type 'add' to add it to your cart!"
        return "Sorry, that item just went out of stock!"