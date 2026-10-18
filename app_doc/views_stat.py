# coding:utf-8
# 文档浏览次数 & 点赞
import uuid

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http.response import JsonResponse
from django.views.decorators.http import require_POST
from loguru import logger

from app_doc.models import Doc, DocLike, DocShare, Project
from app_doc.utils import check_user_project_view_role

VIEW_COOKIE_PREFIX = 'mrdoc_dv_'        # 浏览去重 cookie，同一浏览器 2 小时内只计一次
VIEW_COOKIE_AGE = 60 * 60 * 2
VISITOR_COOKIE = 'mrdoc_vid'            # 游客随机标识，用于点赞去重
VISITOR_COOKIE_AGE = 60 * 60 * 24 * 365


def _visitor_key(request):
    """返回 (访客标识, 需要新写入的游客cookie值或None)"""
    if request.user.is_authenticated:
        return 'u:{}'.format(request.user.id), None
    vid = request.COOKIES.get(VISITOR_COOKIE, '')
    if len(vid) == 32 and vid.isalnum():
        return 'v:' + vid, None
    vid = uuid.uuid4().hex
    return 'v:' + vid, vid


def get_doc_stat(request, doc):
    """模板上下文用：当前访客是否已点赞"""
    key, _new = _visitor_key(request)
    if _new:
        return False
    return DocLike.objects.filter(doc_id=doc.id, visitor_key=key).exists()


def record_doc_view(request, response, doc):
    """在文档页 render 之后调用：计数 + 写去重 cookie。
    使用 queryset.update，不会触发 Doc.modify_time(auto_now) 变化。"""
    try:
        if response.status_code != 200:
            return response
        cookie_name = VIEW_COOKIE_PREFIX + str(doc.id)
        if request.COOKIES.get(cookie_name):
            return response
        Doc.objects.filter(id=doc.id).update(view_count=F('view_count') + 1)
        response.set_cookie(cookie_name, '1', max_age=VIEW_COOKIE_AGE, httponly=True, samesite='Lax')
    except Exception:
        logger.exception('记录文档浏览次数出错')
    return response


def _can_view(request, doc, token):
    if token:  # 通过分享链接访问
        share = DocShare.objects.filter(token=token, is_enable=True, doc_id=doc.id).first()
        if share is None:
            return False
        if share.share_type == 0:
            return True
        return request.COOKIES.get('sharedoc-{}'.format(token)) == share.share_value
    try:
        project = Project.objects.get(id=doc.top_doc)
    except Project.DoesNotExist:
        return False
    if project.role == 0:
        return True
    if project.role == 4:
        return request.user.is_authenticated
    if project.role == 3 and request.COOKIES.get('viewcode-{}'.format(project.id)) == project.role_value:
        return True
    if request.user.is_authenticated:
        return check_user_project_view_role(request.user.id, project.id)
    return False


# 点赞 / 取消点赞（POST，需 CSRF token）
# URL 以 /share_doc 开头，开启"强制登录"时游客也能在分享页点赞
@require_POST
def doc_like(request):
    try:
        doc_id = int(request.POST.get('doc_id', 0))
        doc = Doc.objects.get(id=doc_id, status=1)
    except (ValueError, Doc.DoesNotExist):
        return JsonResponse({'status': False, 'data': '文档不存在'})
    token = request.POST.get('token', '')
    if not _can_view(request, doc, token):
        return JsonResponse({'status': False, 'data': '无权限'})

    key, new_vid = _visitor_key(request)
    liked = False
    try:
        with transaction.atomic():
            obj = DocLike.objects.filter(doc=doc, visitor_key=key).first()
            if obj:  # 已点赞 -> 取消
                obj.delete()
                Doc.objects.filter(id=doc.id, like_count__gt=0).update(like_count=F('like_count') - 1)
            else:
                DocLike.objects.create(doc=doc, visitor_key=key)
                Doc.objects.filter(id=doc.id).update(like_count=F('like_count') + 1)
                liked = True
    except IntegrityError:  # 并发重复点击
        liked = True
    count = Doc.objects.filter(id=doc.id).values_list('like_count', flat=True).first() or 0
    resp = JsonResponse({'status': True, 'liked': liked, 'like_count': count})
    if new_vid:
        resp.set_cookie(VISITOR_COOKIE, new_vid, max_age=VISITOR_COOKIE_AGE, httponly=True, samesite='Lax')
    return resp
