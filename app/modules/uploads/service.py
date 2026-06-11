import asyncio
import cloudinary.uploader
import cloudinary.api
from app.modules.uploads.schemas import CloudinaryResponse
from app.core.exceptions.custom_exceptions import AppError

class UploadService:
    async def upload_image(self, file_bytes: bytes) -> CloudinaryResponse:
        """
        Sube una imagen a Cloudinary delegando la operación a un thread separado.
        """
        try:
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                file_bytes,
                folder="foodstore/productos",
                resource_type="image",
                allowed_formats=["jpg", "jpeg", "png", "webp"],
                overwrite=False,
                unique_filename=True
            )
            return CloudinaryResponse(
                secure_url=result.get("secure_url"),
                public_id=result.get("public_id"),
                width=result.get("width"),
                height=result.get("height"),
                format=result.get("format"),
                resource_type=result.get("resource_type")
            )
        except Exception as e:
            raise AppError(
                code="CLOUDINARY_UPLOAD_ERROR",
                detail=f"Error al subir imagen a Cloudinary: {str(e)}"
            )

    async def delete_image(self, public_id: str) -> None:
        """
        Elimina una imagen de Cloudinary usando su public_id.
        """
        try:
            result = await asyncio.to_thread(cloudinary.uploader.destroy, public_id)
            if result.get("result") not in ["ok", "not found"]:
                # Si el resultado no es ok ni not found, algo falló silenciosamente en Cloudinary
                pass
        except Exception as e:
            raise AppError(
                code="CLOUDINARY_DELETE_ERROR",
                detail=f"Error al eliminar imagen en Cloudinary: {str(e)}"
            )
