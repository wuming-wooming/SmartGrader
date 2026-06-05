"""
Celery 异步图片清洗任务模块
将图片清洗提交给 Celery Worker 后台执行，并更新数据库状态。
清洗完成后自动触发 OCR 识别与切题。

创建者：周康哲
"""
from sqlalchemy import select

from core.celery_app import celery_app
from core.database import SyncSessionLocal
from models.assignment_task import AssignmentTask
from models.async_task import AsyncTask
from services.image_service import _do_opencv_cleaning
from tasks.ocr_tasks import process_ocr_task


def _update_db_status(
    assignment_task_id: int,
    celery_task_id: str,
    status: int,
    processed_file: str = None,
    error: str = None,
):
    """
    同步更新数据库中的任务状态和异步日志状态

    :param assignment_task_id: 作业主表记录ID
    :param celery_task_id: Celery 分配的任务UUID
    :param status: 状态码 (1=处理中, 2=完成, 3=失败)
    :param processed_file: 处理后的图片相对路径URL
    :param error: 错误信息
    """
    with SyncSessionLocal() as db:
        assignment_task = db.get(AssignmentTask, assignment_task_id)
        if assignment_task:
            # assignment_task.task_status = status
            if processed_file:
                assignment_task.processed_file = processed_file
            if error:
                assignment_task.error_msg = error
                assignment_task.task_status = status

        stmt = select(AsyncTask).where(AsyncTask.celery_task_id == celery_task_id)
        result = db.execute(stmt)
        aysnc_log = result.scalars().first()
        if aysnc_log:
            aysnc_log.status = status
            if error:
                aysnc_log.error_detail = error
        else:
            new_log = AsyncTask(
                assignment_task_id=assignment_task_id,
                celery_task_id=celery_task_id,
                status=status,
                error_detail=error if error else None,
            )
            db.add(new_log)

        db.commit()


@celery_app.task(bind=True, name="process_homework_image_task")
def process_homework_image_task(
    self, assignment_task_id: int, input_path: str, output_path: str, processed_url: str
):
    """
    Celery 后台任务：执行图像清洗，并更新数据库状态
    该函数由 Celery Worker 在独立进程中调用

    :param self: Celery任务实例自身 (为了获取 request.id)
    :param assignment_task_id: 刚创建的数据库任务ID
    :param input_path: 硬盘上的原图路径
    :param output_path: 清洗后图片要保存的硬盘路径
    :param processed_url: 清洗后图片对前端暴露的相对URL
    """
    try:
        _update_db_status(
            assignment_task_id,
            self.request.id,
            status=1,
        )

        success = _do_opencv_cleaning(input_path, output_path)

        if success:
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=2,
                processed_file=processed_url,
            )
            # 图片清洗完成后，自动触发OCR识别与切题
            # process_ocr_task.delay(
            #     assignment_task_id=assignment_task_id,
            #     processed_image_path=output_path,
            #     raw_image_path=input_path,
            # )
            return {"status": "success", "task_id": assignment_task_id}
        else:
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error="OpenCV清洗算法失败：无法读取或处理图像",
            )
            return {"status": "failed", "task_id": assignment_task_id}
    except Exception as e:
        try:
            _update_db_status(
                assignment_task_id,
                self.request.id,
                status=3,
                error=f"处理过程发生异常:{str(e)}",
            )
        except Exception as inner_e:
            print(f"更新数据库状态失败: {inner_e}")
        raise e
