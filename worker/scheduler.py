from celery_app import celery_app
from tasks import enqueue_all_products

if __name__ == "__main__":
    result = enqueue_all_products.delay()
    print("Price checking job submitted!")
    print("Task ID:", result.id)