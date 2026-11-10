from rest_framework.exceptions import MethodNotAllowed

class ImmutableDocumentViewSetMixin:
    immutable_document_name = 'سند'

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PUT', detail=f'ویرایش مستقیم {self.immutable_document_name} مجاز نیست.')

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH', detail=f'ویرایش مستقیم {self.immutable_document_name} مجاز نیست.')

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed('DELETE', detail=f'حذف مستقیم {self.immutable_document_name} مجاز نیست.')
