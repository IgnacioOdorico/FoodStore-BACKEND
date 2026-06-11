import urllib.parse
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from app.modules.uploads.schemas import CloudinaryResponse
from app.modules.uploads.service import UploadService
from app.core.deps import require_role

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

def get_upload_service() -> UploadService:
    return UploadService()

@router.post(
    "/imagen",
    response_model=CloudinaryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(["ADMIN"]))]
)
async def upload_image(
    file: UploadFile = File(...),
    svc: UploadService = Depends(get_upload_service)
):
    """Sube una imagen a Cloudinary y retorna la URL segura y el public_id."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no soportado. Permitidos: {ALLOWED_MIME_TYPES}"
        )
    
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen excede el límite de 5 MB."
        )
    
    return await svc.upload_image(file_bytes)

@router.delete(
    "/imagen/{public_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(["ADMIN"]))]
)
async def delete_image(
    public_id: str,
    svc: UploadService = Depends(get_upload_service)
):
    """Elimina una imagen de Cloudinary usando su public_id."""
    decoded_public_id = urllib.parse.unquote(public_id)
    await svc.delete_image(decoded_public_id)
    return None
