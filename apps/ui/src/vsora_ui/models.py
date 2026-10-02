from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class Request(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)


class SimulationRequest(Request):
    kind:Literal['simulation']='simulation'
    model:Literal['point','double','shell','casa']='point'
    stations:Literal[4,8]=8
    layout:Literal['spread','line','ring']='spread'
    duration_s:int=Field(default=3600,ge=60,le=14400,strict=True)
    integration_s:int=Field(default=120,ge=5,le=600,strict=True)
    flux_jy:float=Field(default=1000,gt=0,le=1e7)
    sefd_jy:float=Field(default=10000,gt=0,le=1e9)
    noise:bool=Field(default=False,strict=True)
    seed:int=Field(default=42,ge=0,le=2**32-1,strict=True)

    @model_validator(mode='after')
    def dimensions(self):
        if self.duration_s%self.integration_s:
            raise ValueError('観測時間は積分時間の整数倍にしてください')
        rows=self.duration_s//self.integration_s*self.stations*(self.stations-1)//2
        if rows>4096: raise ValueError('参照画像化は4096基線時刻までです。積分時間を長くしてください')
        return self


class ValidationRequest(Request):
    kind:Literal['validation']='validation'
    validation:Literal['closure','quality','clock','fringe','basic']='quality'


JobRequest=Annotated[SimulationRequest|ValidationRequest,Field(discriminator='kind')]
