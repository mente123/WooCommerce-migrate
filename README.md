# WooCommerce Python Script

A Python script with a CLI that gets all orders (parent and sub orders) and customers (only a specific role = seller) from WC API v3 and submits them to a MongoDB Database. 

The script can be ran on a large store with more than 100K orders and 20K+ customers.

Developed with Python3 and using wc api v3 details:
https://woocommerce.github.io/woocommerce-rest-api-docs/


## Features
- Mutli-threaded (able to get 1000 records once)
- Has Command line interface
- Import records between specific dates
- Show progress of the process using tqdm library
- Import specific order ID or customer ID


## How to use

```
python migration.py --help
```

```
python migration.py orders --help
```

```
python migration.py customers --help
```
