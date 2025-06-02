from rest_framework.response import Response
from rest_framework import status as rest_status


def RESPONSE(message: str, status: bool, status_code: int, response):
    http_status = rest_status.HTTP_500_INTERNAL_SERVER_ERROR
    if status_code == 200:
        http_status = rest_status.HTTP_200_OK
    elif status_code == 201:
        http_status = rest_status.HTTP_201_CREATED
    elif status_code == 404:
        http_status = rest_status.HTTP_404_NOT_FOUND
    else:
        http_status = rest_status.HTTP_400_BAD_REQUEST
    return Response(
        {
            "message": message,
            "status": status,
            "status_code": status_code,
            "response": response,
        },
        status=http_status,
    )
