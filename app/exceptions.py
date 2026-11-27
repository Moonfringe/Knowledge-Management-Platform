import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = err["loc"]
        if err["type"] == "json_invalid":
            field = loc[0]
        else:
            field = ".".join(str(p) for p in loc[1:]) or loc[0]
        errors.append({"field": field, "msg": err["msg"].removeprefix("Value error, ")})
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数校验失败", "errors": errors},
    )


# 框架自己抛的英文文案 → 中文。接口里 raise 的 detail（如"笔记不存在"）不在表里，原样返回
FRAMEWORK_MESSAGES = {
    "Not Found": "资源不存在",
    "Method Not Allowed": "请求方法不允许",
    "Bad Request": "请求不合法",
    "Unauthorized": "未认证",
    "Not authenticated": "未认证，请先通过 /auth/login 换取 token",
    "Forbidden": "无权访问",
    "Internal Server Error": "服务器内部错误",
}


async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException
) -> JSONResponse:
    headers = getattr(exc, "headers", None)
    detail = exc.detail
    if isinstance(detail, str):                     # pragma: no branch  # detail 也可能是 dict，本项目从不这么用
        detail = FRAMEWORK_MESSAGES.get(detail, detail)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={"detail": detail}
    )


async def unhandled_exception_handler(  # pragma: no cover — 没有路由会抛未捕获异常，测不到
        request: Request,
        exc: Exception
) -> JSONResponse:
    logger.exception("未处理异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
