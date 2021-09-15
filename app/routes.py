import datetime
import decimal
import itertools
import random
import re

from dominate.tags import *
from flask import redirect, render_template, request
from werkzeug.utils import secure_filename

from app import ah_bon_OCR, app


def timestamp():
    """Return current timestamp."""
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return stamp


def write_log(message, also_print=False, is_error=False):
    """Write a message to the debug log."""
    with open('logs/app_debug.log','a') as debug_f:
        debug_f.write(f"[{timestamp()}] {message}\n")
    if is_error == True:
        with open('logs/app_error.log','a') as debug_f:
            debug_f.write(f"[{timestamp()}] {message}\n")
    if also_print == True:
        print(message)


def get_ip():
    """Return ip of user."""
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    return ip


def parse_users(post_form):
    """Output list of valid users."""
    out_users = []
    users = post_form.getlist("users[]")
    users = set(users)
    for user in users:
        if not user:
            continue
        user = user.replace(" ", "_")
        re_match = re.fullmatch('[0-9a-zA-Z_]{1,16}', user)
        if re_match:
            out_users.append(user)
    out_users.sort()
    return out_users


def allowed_file(filename):
    """Checks if the filename is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def build_participants_html(receipt, cur_div, price_id):
    """Build HTML for participants."""
    with cur_div:
        for name in receipt.participants:
            with div(style="display:inline", _class="mx-2"):
                button("-", type="button", _class="btn btn-danger btn-sm", onclick=f"decCount('{price_id}_{name}')")
                input_(_class="form-control form-control-sm", type="number", name=f"{price_id}_{name}", id=f"{price_id}_{name}", value="1", size="1")
                button("+", type="button", _class="btn btn-success btn-sm", onclick=f"incCount('{price_id}_{name}')")
    return cur_div


def build_items_html(receipt):
    """Build HTML for shopping items."""
    items_html = div()
    with items_html:
        h4("Boodschappen:")
        input_(_class="form-control form-control-sm", type="text", value="Product", disabled="",
               size="16", style="font-weight:bold")
        input_(_class="form-control form-control-sm", type="text", value="Prijs", size="7", readonly="", style="font-weight:bold")
        for i, user in enumerate(receipt.participants):
            if i % 2 == 1:
                cur_size = "8"
            else:
                cur_size = "9"
            input_(_class="form-control form-control-sm mx-2", type="text", value=user, disabled="",
                   size=cur_size)

    for index, row in receipt.items.iterrows():
        cur_div = div(_class="form-group")  # Item elements of item list
        with cur_div:
            input_(_class="form-control form-control-sm", type="text", value=f"{row['item_text']}", disabled="",
                   size="16")
            if receipt.verify["subtotal"] is True:
                input_(_class="form-control form-control-sm is-valid", type="number", name=f"item_{index}",
                       value=f"{row['price']}", size="4", readonly="")
            else:
                input_(_class="form-control form-control-sm is-invalid", type="number", name=f"item_{index}",
                       value=f"{row['price']}", size="4")
        cur_div = build_participants_html(receipt, cur_div, f"item_{index}")
        items_html.add(cur_div)
    cur_div = div(_class="form-group")  # Subtotal element of item list
    with cur_div:
        input_(_class="form-control form-control-sm", type="text", value="Subtotaal", disabled="", size="16",
               style="font-weight:bold")
        if receipt.verify["subtotal"] is True:
            input_(_class="form-control form-control-sm is-valid", type="number", name="subtotal",
                   value=f"{receipt.subtotal}", size="5", readonly="")
        else:
            input_(_class="form-control form-control-sm is-invalid", type="number", name="subtotal",
                   value=f"{receipt.subtotal}", size="5")
    items_html.add(cur_div)
    items_html.add(br())
    return items_html


def build_bonus_html(receipt):
    """Build HTML for bonus discount."""
    bonus_html = div()
    bonus_html.add(h4("Bonus:"))
    if len(receipt.bonus_items) != 0:
        for index, row in receipt.bonus_items.iterrows():
            cur_div = div(_class="form-group")  # Bonus item elements of bonus item list
            with cur_div:
                input_(_class="form-control form-control-sm", type="text", value=f"{row['bonus_text']}", disabled="",
                       size="16")
                if receipt.verify["bonus"] is True:
                    input_(_class="form-control form-control-sm is-valid", type="number", name=f"bonus_item_{index}",
                           value=f"{row['price']}", size="4", readonly="")
                else:
                    input_(_class="form-control form-control-sm is-invalid", type="number", name=f"bonus_item_{index}",
                           value=f"{row['price']}", size="4")
            cur_div = build_participants_html(receipt, cur_div, f"bonus_item_{index}")
            bonus_html.add(cur_div)
    cur_div = div(_class="form-group")  # Bonus total element of bonus item list
    with cur_div:
        input_(_class="form-control form-control-sm", type="text", value="Uw voordeel", disabled="", size="16",
               style="font-weight:bold")
        if receipt.verify["bonus"] is True:
            input_(_class="form-control form-control-sm is-valid", type="number", name="bonus",
                   value=f"{receipt.bonus}", size="4", readonly="")
        else:
            input_(_class="form-control form-control-sm is-invalid", type="number", name="bonus",
                   value=f"{receipt.bonus}", size="4")
    bonus_html.add(cur_div)
    bonus_html.add(br())
    return bonus_html


def build_total_html(receipt):
    """Build HTML for total price."""
    total_html = div()
    with total_html:
        with div(_class="form-group"):  # Total element
            input_(_class="form-control form-control-sm", type="text", value="Totaal", disabled="", size="16",
                   style="font-weight:bold")
            if receipt.verify["total"] is True:
                input_(_class="form-control form-control-sm is-valid", type="number", name="total",
                       value=f"{receipt.total}", size="5", readonly="")
            else:
                input_(_class="form-control form-control-sm is-invalid", type="number", name="total",
                       value=f"{receipt.total}", size="5")
            input_(type="hidden", name="participants", value=",".join(receipt.participants))
            input_(type="hidden", name="nr_items", value=len(receipt.items))
            input_(type="hidden", name="nr_bonus_items", value=len(receipt.bonus_items))
            button("Bereken splitsing", type="submit", _class="btn btn-info btn-sm mx-3")
        br()
    return total_html


def format_price(price):
    """Format prices."""
    price = price.replace(",", ".")
    price = decimal.Decimal(price)
    cents = decimal.Decimal('.01')
    return price.quantize(cents, decimal.ROUND_HALF_UP)


def process_form(receipt_form):
    """Process submitted form. Uses a point system to make sure single cents that can't be split will be divided fairly."""
    ONE_CENT = decimal.Decimal("0.01")
    item_sum = 0
    bonus_sum = 0
    receipt_dic = {}
    receipt_dic["participants"] = receipt_form["participants"].split(",")
    receipt_dic["nr_items"] = int(receipt_form["nr_items"])
    receipt_dic["nr_bonus_items"] = int(receipt_form["nr_bonus_items"])
    receipt_dic["subtotal"] = format_price(receipt_form["subtotal"])
    receipt_dic["bonus"] = format_price(receipt_form["bonus"])
    receipt_dic["total"] = format_price(receipt_form["total"])
    receipt_dic["user_totals"] = {}
    for user in receipt_dic["participants"]:  # Innit totals for every user
        receipt_dic["user_totals"][user] = 0
    receipt_dic["leftover_points"] = {}  # dict that keeps track of who is assinged 1 cent extra because they cannot be split
    for i in range(2, len(receipt_dic["participants"]) + 1): # Loop over all combinations of 2 or more users
        for subset in itertools.combinations(receipt_dic["participants"], i):  # Generate combination of i users
            comb_key = tuple(subset)
            receipt_dic["leftover_points"][comb_key] = {}  # create a point dict for every combination of users
            for user in subset:  # create a dict for every user that occurs in a certain combination of users
                receipt_dic["leftover_points"][comb_key][user] = 0  # Start with 0 points
    # Start processing shoping items
    for itemtype in ["nr_items", "nr_bonus_items"]:
        for i in range(receipt_dic[itemtype]):  # Loop over items
            if itemtype == "nr_items":
                item_key = f"item_{i}"
            elif itemtype == "nr_bonus_items":
                item_key = f"bonus_item_{i}"
            item_price = format_price(receipt_form[item_key])
            if itemtype == "nr_items":
                item_sum += item_price
            elif itemtype == "nr_bonus_items":
                bonus_sum += item_price
            cur_shares = {}
            for user in receipt_dic["participants"]:  # get the num of shares each users has for this item
                user_shares = int(receipt_form[f"{item_key}_{user}"])
                if user_shares > 0:
                    cur_shares[user] = user_shares
            if len(cur_shares) == 0:
                raise Exception  # TODO return error (an item without any users)
            elif len(cur_shares) == 1:  # Only 1 user pays for the item, don't have to split the price
                if itemtype == "nr_items":
                    receipt_dic["user_totals"][next(iter(cur_shares))] += item_price
                elif itemtype == "nr_bonus_items":
                    receipt_dic["user_totals"][next(iter(cur_shares))] -= item_price
                continue  # Done with this item

            total_shares = sum(cur_shares.values())
            leftover_amount = item_price % (total_shares * ONE_CENT)  # Amount that cannot be divided in whole cents
            share_price = (item_price - leftover_amount) / total_shares  # Calculate price per share
            for user in cur_shares:  # Add the amount for the shares they have
                if itemtype == "nr_items":
                    receipt_dic["user_totals"][user] += (cur_shares[user] * share_price)
                elif itemtype == "nr_bonus_items":
                    receipt_dic["user_totals"][user] -= (cur_shares[user] * share_price)
            # Divide leftover amount using a point system
            comb_key = tuple(sorted(cur_shares.keys()))  # Combination of partaking users that serves as a key in receipt_dic["leftover_points"]
            for _ in range(int(leftover_amount / ONE_CENT)):  # For every cent that still has to be divided
                if itemtype == "nr_items":
                    outer_val = min(receipt_dic["leftover_points"][comb_key].values())  # Min point value
                elif itemtype == "nr_bonus_items":
                    outer_val = max(receipt_dic["leftover_points"][comb_key].values())  # Max point value
                
                outer_users = [k for k, v in receipt_dic["leftover_points"][comb_key].items() if v == outer_val]  # select user(s) that gets the next cent assigned
                sel_user = random.choice(outer_users)  # Select randomly if multiple users have the same amount of points
                if itemtype == "nr_items":
                    receipt_dic["leftover_points"][comb_key][sel_user] += 1 / cur_shares[sel_user]  # Give the user points proportional to the shares he has
                    receipt_dic["user_totals"][sel_user] += ONE_CENT  # User is assigned 1 leftover cent
                elif itemtype == "nr_bonus_items":
                    receipt_dic["leftover_points"][comb_key][sel_user] -= 1 / cur_shares[sel_user]  # Give the user points proportional to the shares he has
                    receipt_dic["user_totals"][sel_user] -= ONE_CENT  # User is assigned 1 leftover cent
    # Verify totals
    error = False
    if receipt_dic["subtotal"] != item_sum:
        error = True  # TODO log
    if receipt_dic["bonus"] != bonus_sum:
        error = True  # TODO log
    if (receipt_dic["subtotal"] - receipt_dic["bonus"]) != receipt_dic["total"]:
        error = True  # TODO log
    users_sum = 0
    for user in receipt_dic["user_totals"]:
        users_sum += receipt_dic["user_totals"][user]
    if receipt_dic["total"] == users_sum:
        print("user totals add up") # TODO log
    else:
        error = True  # TODO log
    return receipt_dic, error


def build_result_html(receipt_dic):
    """Build HTML for the result page."""
    result_html = div(_class="container-md")
    with result_html:
        with table(_class="table table-hover"):
            with thead():
                with tr():
                    th("Deelnemer", scope="col")
                    th("Bedrag", scope="col")
            with tbody():
                for user in receipt_dic["user_totals"]:
                    with tr():
                        td(user)
                        td(f"€ {receipt_dic['user_totals'][user]}")
                with tr(_class="table-primary"):
                    td("Totaal")
                    td(f"€ {receipt_dic['total']}")
    return result_html


# Setup vars
ALLOWED_EXTENSIONS = {'pdf',}
SUPERMARKETS = {"AH",}

# Routing
@app.route('/', methods=['GET'])
def root_page():
    return redirect("/Bon_Splitser")


@app.route('/Bon_Splitser', methods=['POST', 'GET'])
def submit():
    ip = get_ip()
    if request.method == 'GET':  # GET means first time loading, otherwise assume POST and expect receipt submission
        return render_template('submit.html')

    assert request.method == "POST"
    supermarket = request.form["supermarket"]
    if supermarket not in SUPERMARKETS:  # Verify supermarket selection
        return render_template('submit.html')  # TODO ERROR

    users = parse_users(request.form)
    if len(users) < 2:
        error_msg = "Voeg minimaal 2 deelnemers toe"
        return render_template('submit.html', error=error_msg)

    if 'file' not in request.files:
        return render_template('submit.html')  # TODO ERROR
    input_pdf = request.files['file']
    if input_pdf.filename == '':  # If the user does not select a file, the browser submits an empty file without name.
        return render_template('submit.html')  # TODO ERROR
    input_pdf.filename = secure_filename(input_pdf.filename)
    if not allowed_file(input_pdf.filename):
        return render_template('submit.html')  # TODO ERROR
        #filename = secure_filename(input_pdf.filename)
    receipt = ah_bon_OCR.process_receipt(input_pdf.stream.read(), supermarket, users)
    # Construct HTML form
    html_form = form(_class="form-inline", action="/Bon_Splitser/result", method="post")
    html_form.add(build_items_html(receipt))
    html_form.add(build_bonus_html(receipt))
    html_form.add(build_total_html(receipt))
    return render_template("adjust.html", html_form=html_form)


@app.route('/Bon_Splitser/result', methods=['POST'])
def display_result():
    receipt_dic, error = process_form(request.form)
    if error:
        return render_template("result.html", error="De som van de bedragen klopt niet.")
    result_html = build_result_html(receipt_dic)
    return render_template("result.html", result_html=result_html)


@app.errorhandler(404)
def notfound_handler(e):
    return render_template('404.html', title='Page Not Found'), 404