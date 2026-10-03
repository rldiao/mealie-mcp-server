from pydantic import BaseModel, StrictBool


class AIProviderCapabilities(BaseModel):
    aiEnabled: StrictBool
    imageProviderEnabled: StrictBool
    audioProviderEnabled: StrictBool
