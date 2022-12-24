"""
Module to import all products or specific product from WooCommerce
"""
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
from dateutil import parser as dateparser
from config import DB, APP
from connections import wcapi, db

MAX_THREADS = APP.MAX_THREADS
max_product_per_page = 100

# list of products ids that are in the database currently
products_in_db = set()

num_of_written_records = 0
num_of_skipped_records = 0


def get_products_in_db(from_date, to_date):
    """Get all products in the range given that are in the database."""
    # Mongo friendly datetime
    from_date = dateparser.isoparse(from_date)
    to_date = dateparser.isoparse(to_date)
    results = db[DB.PRODUCT_COLLECTION].find(
        {"date_created": {"$gte": from_date, "$lte": to_date}},
    )
    return results


def import_all_products(sort, from_date, to_date, sync=False):
    """
    Import all products between from_date and to_date

    params:
    sort: str - Sort products ascending or descending.
    from_date: str - import products submitted starting from this date
    to_date: str - import products submitted untill this date

    returns: list of products
    """
    global num_of_skipped_records, num_of_written_records

    if sync == True:
        # get all products that are in the database first
        results = get_products_in_db(from_date, to_date)
        for product in results:
            products_in_db.add(product.get("id"))

    print("Products found in DB: ", len(products_in_db))

    after = datetime.fromisoformat(from_date)
    before = datetime.fromisoformat(to_date)

    page = 1
    initial_products = wcapi.get(
        "products",
        params={
            "per_page": max_product_per_page,
            "after": after.isoformat(),
            "before": before.isoformat(),
            "page": page,
            "order": sort,
        },
    )
    total_pages = initial_products.headers.get("X-WP-TotalPages", 0)
    print(f"Total pages: {total_pages}\n")
    pages = range(1, int(total_pages) + 1)

    # use multi-threading to pull multiple products concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_product = {
            executor.submit(get_products, page, sort, after, before): page
            for page in pages
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_product),
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


def get_products(page, sort, after, before):
    """Get products on a specific page."""
    try:
        response = wcapi.get(
            "products",
            params={
                "per_page": max_product_per_page,
                "after": after.isoformat(),
                "before": before.isoformat(),
                "page": page,
                "order": sort,
            },
        )
        if response.status_code != 200:
            print(f"Error status code {response.status_code} for page {page}")
        else:
            products = tuple(response.json())
            for product in products:
                process_product(product)

            products = None  # clear previous values to free up memeory
            return True
    except Exception as e:
        print(f"Unexpected Error: {e}")
    return False


def process_product(product):
    """
    Process product to convert date and times to datetime objects
    and insert to MongoDB database
    """
    global num_of_skipped_records, num_of_written_records

    if not product.get("id", None):
        print("No product id skipping")
        return

    date_fields = [
        "date_created",
        "date_created_gmt",
        "date_modified",
        "date_modified_gmt",
        "date_on_sale_from",
        "date_on_sale_from_gmt",
        "date_on_sale_to",
        "date_on_sale_to_gmt",
    ]
    image_date_fields = date_fields[:4]
    for field in date_fields:
        if field not in product:
            continue
        str_date = product[field]
        if not str_date:
            continue
        product[field] = dateparser.isoparse(str_date)

    for field in image_date_fields:
        for i in range(len(product["images"])):
            if field not in product["images"][i]:
                continue
            str_date = product["images"][i][field]
            if not str_date:
                continue
            product["images"][i][field] = dateparser.isoparse(str_date)

    product_id = product.get("id")
    if product_id not in products_in_db:
        db[DB.PRODUCT_COLLECTION].find_one_and_replace(
            filter={"id": product_id}, replacement=product, upsert=True
        )
        num_of_written_records += 1
    else:
        # print(f"Product id: {product_id} found in DB (skipping)")
        num_of_skipped_records += 1


def get_product(id):
    """Get specific product specified by ID."""
    product = wcapi.get(f"products/{id}").json()
    if not product.get("id", None):
        print("No product id skipping")
        return

    date_fields = [
        "date_created",
        "date_created_gmt",
        "date_modified",
        "date_modified_gmt",
        "date_on_sale_from",
        "date_on_sale_from_gmt",
        "date_on_sale_to",
        "date_on_sale_to_gmt",
    ]
    for field in date_fields:
        if field not in product:
            continue
        str_date = product[field]
        if not str_date:
            continue
        product[field] = dateparser.isoparse(str_date)

    image_date_fields = date_fields[:4]
    for field in image_date_fields:
        for i in range(len(product["images"])):
            if field not in product["images"][i]:
                continue
            str_date = product["images"][i][field]
            if not str_date:
                continue
            product["images"][i][field] = dateparser.isoparse(str_date)

    db[DB.PRODUCT_COLLECTION].find_one_and_replace(
        filter={"id": product.get("id")}, replacement=product, upsert=True
    )
