"""
Moudle to import all orders or specific order from WooCommerce
"""
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
from dateutil import parser as dateparser
from config import DB, APP
from connections import wcapi, db

MAX_THREADS = APP.MAX_THREADS
max_order_per_page = 100

# list of orders ids that are in the database currently
orders_in_db = set()

num_of_written_records = 0
num_of_skipped_records = 0


def get_orders_in_db(from_date, to_date):
    """Get all orders in the range given that are in the database."""
    # Mongo friendly datetime
    from_date = dateparser.isoparse(from_date)
    to_date = dateparser.isoparse(to_date)
    results = db[DB.ORDER_COLLECTION].find(
        {"date_created": {"$gte": from_date, "$lte": to_date}},
    )
    return results


def import_all_orders(sort, from_date, to_date, sync=False):
    """
    Import all orders between from_date and to_date

    params:
    sort: str - Sort orders ascending or descending.
    from_date: str - import orders submitted starting from this date
    to_date: str - import orders submitted untill this date

    returns: list of orders
    """
    global num_of_skipped_records, num_of_written_records

    if sync == True:
        # get all orders that are in the database first
        results = get_orders_in_db(from_date, to_date)
        for order in results:
            orders_in_db.add(order.get("id"))

    print("Orders found in DB: ", len(orders_in_db))

    after = datetime.fromisoformat(from_date)
    before = datetime.fromisoformat(to_date)

    page = 1
    initial_orders = wcapi.get(
        "orders",
        params={
            "per_page": max_order_per_page,
            "after": after.isoformat(),
            "before": before.isoformat(),
            "page": page,
            "order": sort,
        },
    )
    total_pages = initial_orders.headers.get("X-WP-TotalPages", 0)
    print(f"Total pages: {total_pages}\n")
    pages = range(1, int(total_pages) + 1)

    # use multi-threading to pull multiple orders concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_order = {
            executor.submit(get_orders, page, sort, after, before): page
            for page in pages
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_order),
            total=int(total_pages),
            unit="page",
        ):
            try:
                status = future.result()
            except:
                pass

    print(f'\n\n{"-" * 50}')
    print(f"Newly inserted records: {num_of_written_records}")
    print(f"Skipped records: {num_of_skipped_records}\n")


def get_orders(page, sort, after, before):
    """Get orders on a specific page."""
    try:
        response = wcapi.get(
            "orders",
            params={
                "per_page": max_order_per_page,
                "after": after.isoformat(),
                "before": before.isoformat(),
                "page": page,
                "order": sort,
            },
        )
        if response.status_code != 200:
            print(f"Error status code {response.status_code} for page {page}")
        else:
            orders = tuple(response.json())
            for order in orders:
                process_order(order)

            orders = None  # clear previous values to free up memeory
            return True
    except Exception as e:
        print(f"Unexpected Error: {e}")
    return False


def process_order(order):
    """
    Process order to convert date and times to datetime objects
    and insert to MongoDB database
    """
    global num_of_skipped_records, num_of_written_records

    if not order.get("id", None):
        print("No order id skipping")
        return

    date_fields = [
        "date_created",
        "date_created_gmt",
        "date_modified",
        "date_modified_gmt",
        "date_paid",
        "date_paid_gmt",
        "date_completed",
        "date_completed_gmt",
    ]
    for field in date_fields:
        if field not in order:
            continue
        str_date = order[field]
        if not str_date:
            continue
        order[field] = dateparser.isoparse(str_date)

    order_id = order.get("id")
    if order_id not in orders_in_db:
        db[DB.ORDER_COLLECTION].find_one_and_replace(
            filter={"id": order_id}, replacement=order, upsert=True
        )
        num_of_written_records += 1
    else:
        # print(f"Order id: {order_id} found in DB (skipping)")
        num_of_skipped_records += 1


def get_order(id):
    """Get specific order specified by ID."""
    order = wcapi.get(f"orders/{id}").json()
    if not order.get("id", None):
        print("No order id skipping")
        return

    date_fields = [
        "date_created",
        "date_created_gmt",
        "date_modified",
        "date_modified_gmt",
        "date_paid",
        "date_paid_gmt",
        "date_completed",
        "date_completed_gmt",
    ]
    for field in date_fields:
        if field not in order:
            continue
        str_date = order[field]
        if not str_date:
            continue
        order[field] = dateparser.isoparse(str_date)

    db[DB.ORDER_COLLECTION].find_one_and_replace(
        filter={"id": order.get("id")}, replacement=order, upsert=True
    )
