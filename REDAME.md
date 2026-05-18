运行项目

添加了 redis, 新增了同步数据库适配celery, 运行前启动 mysql 修改数据库的密码

pip install -r requirements.txt

uvicorn main:app --reload

celery -A core.celery_app worker -l info -P eventlet
