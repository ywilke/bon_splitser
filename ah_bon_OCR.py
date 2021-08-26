import fitz
import io
import PIL.Image as Image
import numpy as np
import pandas as pd
import cv2
import pytesseract
import re
import decimal


class Receipt:
    subtotal = 0
    subtotal_conf = None
    bonus = 0
    bonus_conf = None
    total = 0
    total_conf = None
    items = []
    bonus_items = []

    def __init__(self, supermarket, participants):
        self.supermarket = supermarket
        self.participants = participants

    def add_item(self, price, price_conf, bonus, item_text):
        """Add item to receipt."""
        self.items.append(pd.DataFrame([{"price": price, "price_conf": price_conf, "bonus": bonus, "item_text": item_text}]))

    def add_bonus_item(self, bonus_price, price_conf, bonus_text):
        """Add bonus item to receipt."""
        self.bonus_items.append(pd.DataFrame([{"price": bonus_price, "price_conf": price_conf, "bonus_text": bonus_text}]))

    def merge_items(self):
        """Concat dfs of parsed items."""
        self.items = pd.concat(self.items)
        self.items.reset_index(drop=True, inplace=True)
        if self.bonus_items:
            self.bonus_items = pd.concat(self.bonus_items)
            self.bonus_items.reset_index(drop=True, inplace=True)

    def verify_prices(self):
        """Check if all the totals match."""
        subtotal = self.items["price"].sum() == self.subtotal
        if len(self.bonus_items) > 0:
            bonus = self.bonus_items["price"].sum() == self.bonus
        else:
            bonus = True
        total = (self.subtotal - self.bonus) == self.total
        totals = {"subtotal": subtotal, "bonus": bonus, "total": total}
        self.verify = totals
        if sum(totals.values()) == len(totals):
            print("All items and totals add up.")
        else:
            for key, correct in totals:
                if not correct:
                    print(f"{key} does not add up!")


def img_from_pdf(pdf):
    doc = fitz.open(pdf)
    xref = doc.getPageImageList(0)[0][0]  # Locate xref of first image in first page
    img_data = doc.extract_image(xref)
    image = Image.open(io.BytesIO(img_data["image"]))
    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)  # Convert from PIL image to cv2 image
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    #cv2.imwrite('tmp_data/OCR.png', image)
    return image


def receipt_ocr(image):
    ocr_out = pytesseract.image_to_data(image, config="--psm 6", lang="nld", output_type=pytesseract.Output.DATAFRAME)
    df = ocr_out[["page_num", "block_num", "par_num", "line_num", "word_num", "conf", "text", "left", "width", "top", "height"]]
    df = df[df["conf"] > 0]
    # Create global line numbering
    line_id = df["page_num"].astype(str) + "-" + df["block_num"].astype(str) + "-" + df["par_num"].astype(str) + "-" + \
              df["line_num"].astype(str)
    codes, uniques = pd.factorize(line_id)
    df["global_line"] = codes
    df = df.drop(columns=["page_num", "block_num", "par_num", "line_num"])  # Remove some columns
    return df


def remove_noise(image):
    return cv2.medianBlur(image, 5)


def parse_start(line, df_line):
    for index, row in df_line.iterrows():  # Loop over words
        if row["text"].upper() == "AANTAL" or row["text"].upper() == "OMSCHRIJVING" or row["text"].upper() == "PRIJS" or row["text"].upper() == "BEDRAG":
            return "parse_items"
    return "start"


def ah_price(price):
    """Format prices from AH supermarket"""
    price = price.replace(",", ".")
    if "." not in price:
        price = f"{price[0:-2]}.{price[-2:]}"  # Insert decimal before the last 2 digits if not present
    price = decimal.Decimal(price)
    cents = decimal.Decimal('.01')
    return price.quantize(cents, decimal.ROUND_HALF_UP)


def parse_items(bonuskaart_skip, line, df_line, receipt):
    # Check for bonuskaart line
    if bonuskaart_skip == False:
        for index, row in df_line.iterrows():  # Loop over words
            if row["text"].upper() == "BONUSKAART":
                return True, "parse_items", receipt  # Skip bonuskaart check from now on
    # Check for subtotal line
    for index, row in df_line.iterrows():  # Loop over words
        if row["text"].upper() == "SUBTOTAAL":
            receipt.subtotal = ah_price(df_line.iloc[-1]["text"])
            receipt.subtotal_conf = df_line.iloc[-1]["conf"]
            return bonuskaart_skip, "parse_bonus", receipt

    # Get price and bonus info
    bonus = None
    price_loc = -1
    last_row = df_line.iloc[price_loc]
    for bonus_id in ["B", "35%"]: # Check for bonus and 35% discount
        if bonus_id in last_row["text"].upper():  # Check if bonus present
            bonus = bonus_id
            if bonus_id == last_row["text"].upper():  # If word only contains the bonus_id and not the price
                price_loc = -2
                price_row = df_line.iloc[price_loc]  # Price row is the word before bonus_id
            else:  # Price and bonus_id are in the same word. Need to extract price
                last_row["text"] = last_row["text"].replace(bonus_id, "").replace(" ", "")  # Remove bonus_id and spaces
                price_row = last_row
            break
    else:
        price_row = last_row
    price = ah_price(price_row["text"])
    price_conf = price_row["conf"]

    # Get item text
    price_re = "\d{1,2},\d{2}"
    item_text = ""
    for index, row in df_line.iloc[0:price_loc].iterrows():  # Loop over words before price
        if re.match(price_re, row["text"]):  # Skip price of single item
            continue
        else:
            item_text = f"{item_text} {row['text']}"
    receipt.add_item(price, price_conf, bonus, item_text)
    return bonuskaart_skip, "parse_items", receipt


def parse_bonus(line, df_line, receipt):
    # Check for bonus total
    for index, row in df_line.iterrows():  # Loop over words
        if row["text"].upper() == "VOORDEEL":
            receipt.bonus = ah_price(df_line.iloc[-1]["text"])
            receipt.bonus_conf = df_line.iloc[-1]["conf"]
            return "parse_total", receipt
    # Parse bonus items
    bonus_price = ah_price(df_line.iloc[-1]["text"].replace("-", ""))
    price_conf = df_line.iloc[-1]["conf"]
    bonus_text = df_line.iloc[0:-1]["text"].str.cat(sep=" ").upper()  # Merge bonus text
    bonus_text = bonus_text.replace("BONUS", "").replace("35% K", "")
    receipt.add_bonus_item(bonus_price, price_conf, bonus_text)
    return "parse_bonus", receipt


def parse_total(line, df_line, receipt):
    for index, row in df_line.iterrows():  # Loop over words
        if row["text"].upper() == "TOTAAL":
            receipt.total = ah_price(df_line.iloc[-1]["text"])
            receipt.total_conf = df_line.iloc[-1]["conf"]
            return "end", receipt
    return "parse_total", receipt

def main():
    # Variables
    pdf_path = "test_data/input_pdf/ah_02.pdf"

    # Create instance of receipt
    receipt = Receipt(supermarket="AH", participants=["Alice", "Bob"])
    # Read receipt
    image = img_from_pdf(pdf_path)
    df = receipt_ocr(image)

    parse_stage = "start"
    bonuskaart_skip = False
    grouped = df.groupby(["global_line"])
    for name, df_group in grouped:  # Loop over lines
        if parse_stage == "start":
            parse_stage = parse_start(name, df_group)
        elif parse_stage == "parse_items":
            bonuskaart_skip, parse_stage, receipt = parse_items(bonuskaart_skip, name, df_group, receipt)
        elif parse_stage == "parse_bonus":
            parse_stage, receipt = parse_bonus(name, df_group, receipt)
        elif parse_stage == "parse_total":
            parse_stage, receipt = parse_total(name, df_group, receipt)

    receipt.merge_items()
    receipt.verify_prices()
    return receipt


if __name__ == "__main__":
    receipt = main()
