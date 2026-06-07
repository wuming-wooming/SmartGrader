import redis

# 连接 Redis（本地默认配置）
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
r_db1 = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)

# 定义要清理的键模式
patterns = ["celery*", "_kombu.binding*"]

def clean_redis(db, patterns):
    for pattern in patterns:
        # 用 SCAN 遍历，非阻塞
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = db.scan(cursor, pattern, count=1000)
            if keys:
                db.unlink(*keys)  # 批量异步删除
                deleted += len(keys)
            if cursor == 0:
                break
        print(f"已删除 {deleted} 个匹配 '{pattern}' 的键")

if __name__ == "__main__":
    # 清理 db0 和 db1
    clean_redis(r, patterns)
    clean_redis(r_db1, patterns)