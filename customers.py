"""
Module to import all customers or specific customer from WooCommerce
"""
import concurrent.futures
from tqdm import tqdm
from dateutil import parser as dateparser
from config import APP, DB
from connections import wcapi, db

MAX_THREADS = APP.MAX_THREADS
max_customer_per_page = 100

# list of customer ids that are in the database currently
customers_in_db = set()

num_of_written_records = 0
num_of_skipped_records = 0


def get_customers_in_db(from_date, to_date):
    """Get all customers in the range given that are in the database."""
    # Mongo friendly datetime
    from_date = dateparser.isoparse(from_date)
    to_date = dateparser.isoparse(to_date)
    results = db[DB.CUSTOMER_COLLECTION].find(
        {"date_created": {"$gte": from_date, "$lte": to_date}},
    )
    return results


def import_all_customers(sort, from_date, to_date, sync=False):
    """
    Import all customers having seller role

    params:
    sort: str - Sort customers ascending or descending.
    from_date: str - import customers created starting from this date
    to_date: str - import customers created untill this date

    returns: list of customers have seller role
    """
    global num_of_skipped_records, num_of_written_records

    if sync == True:
        # get all customers that are in the database first
        results = get_customers_in_db(from_date, to_date)
        for order in results:
            customers_in_db.add(order.get("id"))

    print("Customers found in DB: ", len(customers_in_db))

    page = 1
    initial_customers = wcapi.get(
        "customers",
        params={
            "per_page": max_customer_per_page,
            "page": page,
            "role": "seller",
        },
    )

    total_pages = initial_customers.headers.get("X-WP-TotalPages", 0)
    print(f"Total pages: {total_pages}\n")
    pages = range(1, int(total_pages) + 1)

    # use multi-threading to pull multiple customers concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_customer = {
            executor.submit(get_customers, page, sort, from_date, to_date): page
            for page in pages
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_customer),
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


def get_customers(page, sort, from_date, to_date):
    """Get customers on a specific page."""
    try:
        response = wcapi.get(
            "customers",
            params={
                "per_page": max_customer_per_page,
                "page": page,
                "order": sort,
                "role": "seller",
            },
        )
        if response.status_code != 200:
            print(f"Error status code {response.status_code} for page {page}")
        else:
            customers = tuple(response.json())
            for customer in customers:
                process_customer(customer, from_date, to_date)

            customers = None  # clear previous values to free up memory
            return True
    except Exception as e:
        print(f"Unexpected Error: {e}")
    return False


def process_customer(customer, from_date, to_date):
    """
    Process customer to convert date and times to datetime objects
    and import customers created between the specified date
    """
    global num_of_skipped_records, num_of_written_records

    if not customer.get("id", None):
        print("No customer id skipping")
        return

    if from_date <= customer["date_created"] <= to_date:
        date_fields = [
            "date_created",
            "date_created_gmt",
            "date_modified",
            "date_modified_gmt",
        ]
        for field in date_fields:
            if field not in customer:
                continue
            str_date = customer[field]
            if not str_date:
                continue
            customer[field] = dateparser.isoparse(str_date)

        customer_id = customer.get("id")
        if customer_id not in customers_in_db:
            db[DB.CUSTOMER_COLLECTION].find_one_and_replace(
                filter={"id": customer_id}, replacement=customer, upsert=True
            )
            num_of_written_records += 1
        else:
            # print(f"Customer id: {customer_id} found in db (skipping)")
            num_of_skipped_records += 1


def get_customer(id):
    """Get specific customer specified by ID."""
    customer = wcapi.get(f"customers/{id}").json()
    if not customer.get("id", None):
        print("No customer id skipping")
        return

    date_fields = [
        "date_created",
        "date_created_gmt",
        "date_modified",
        "date_modified_gmt",
    ]
    for field in date_fields:
        if field not in customer:
            continue
        str_date = customer[field]
        if not str_date:
            continue
        customer[field] = dateparser.isoparse(str_date)

    db[DB.CUSTOMER_COLLECTION].find_one_and_replace(
        filter={"id": customer.get("id")}, replacement=customer, upsert=True
    )
