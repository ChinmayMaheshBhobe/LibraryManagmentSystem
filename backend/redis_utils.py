import redis

# Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Function to get Redis client instance
def get_redis_client():
    return redis_client
