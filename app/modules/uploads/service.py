import cloudinary.uploader
import cloudinary.api
from app.modules.uploads.schemas import CloudinaryResponse
from app.core.exceptions.custom_exceptions import AppError

def upload_image(file_bytes: bytes) -> CloudinaryResponse:
    """
    Sube una imagen a Cloudinary y devuelve sus metadatos.
    """
    try:
        # Se envía file_bytes en lugar de la ruta del archivo.
        # Las opciones configuran la subida según el TPI.
        result = cloudinary.uploader.upload(
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

def delete_image(public_id: str) -> None:
    """
    Elimina una imagen de Cloudinary usando su public_id.
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        if result.get("result") != "ok":
            # Puede ser 'not found' u otro.
            # Según TPI podemos devolver 204 incluso si no existía, o loguearlo.
            pass
    except Exception as e:
        raise AppError(
            code="CLOUDINARY_DELETE_ERROR",
            detail=f"Error al eliminar imagen en Cloudinary: {str(e)}"
        )
