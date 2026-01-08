from fastapi import FastAPI,File,UploadFile,HTTPException, Form, Depends
from app.schemas import PostCreate, PostResponse, UserRead, UserCreate, UserUpdate
from app.db import Post, create_db_and_tables, get_async_session,User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import imagekit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
import shutil ## (used for file operations like copy,move,delete)
import os
import uuid #(Generate Unique ID's)
import tempfile   #create auto clean up temp files
from typing import List
from fastapi import Form
from typing import Optional
from app.users import auth_backend, current_active_user, fastapi_users

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# for app we connect diff auth endpoints to our fastapi user endpoint
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/auth/jwt', tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])



## Creating post and saving it to the database
@app.post("/upload", tags=["main APIS"])
async def upload_file(
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        # Your existing caption fix
        if caption is None:
            caption = ""
        elif isinstance(caption, (list, tuple)):
            caption = caption[0] if caption else ""
        else:
            caption = str(caption).strip()

        print(f"Final caption: '{caption}' (type: {type(caption)})")


        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
                temp_file_path = temp_file.name
                shutil.copyfileobj(file.file, temp_file)

            upload_result = imagekit.upload_file(
                file=open(temp_file_path, "rb"),
                file_name=file.filename,
                options=UploadFileRequestOptions(
                    use_unique_file_name=True,
                    tags=["backend-upload"]
                )
            )

            if upload_result.response_metadata.http_status_code == 200:
                post = Post(
                    user_id=user.id,
                    caption=caption,
                    url=upload_result.url,
                    file_type="video" if file.content_type.startswith("video/") else "image",
                    file_name=upload_result.name,
                )

                session.add(post)
                await session.commit()
                await session.refresh(post)
                return post

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if not file.file.closed:
                file.file.close()

    except Exception as e:
        import traceback
        print("ERROR in upload_file:")
        traceback.print_exc()  # This will print full error to console
        raise HTTPException(status_code=500, detail=str(e))


#Retreiving from the database
# we are doing this bcz we need to access the database and get all the posts
@app.get("/feed", tags=["main APIS"])
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user),
):
    #fetch users
    user_result = await session.execute(select(User))
    users = user_result.scalars().all()
    user_dict = {u.id: u.email for u in users}

    # Fetch posts
    post_result = await session.execute(select(Post))
    posts = post_result.scalars().all()

    posts_data =[]
    for post in posts:
        posts_data.append(
            {
                "id" : str(post.id),
                "user_id": str(post.user_id),
                "caption" : post.caption,
                "url" : post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id, "Unknown")

            }
        )
    return{"posts": posts_data}

# deleting the post
@app.delete("/posts/{post_id}", tags=["main APIS"])
async def delete_post(post_id: str, session: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    try:
        post_uuid = uuid.UUID(post_id)

        result= await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")

        await session.delete(post)
        await session.commit()

        return {"success": True, "message": "Post deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))