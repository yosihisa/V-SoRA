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
    validation:Literal['rate','closure','quality','clock','fringe','basic']='quality'


class RmlRequest(Request):
    kind:Literal['rml']='rml'
    model:Literal['double','shell','casa']='shell'
    stations:Literal[4,8]=8
    layout:Literal['spread','line','ring']='spread'
    duration_s:int=Field(default=14400,ge=60,le=14400,strict=True)
    integration_s:Literal[.1,.3,1.,3.]=.3
    snapshots:int=Field(default=16,ge=8,le=32,strict=True)
    flux_jy:float=Field(default=1000,gt=0,le=1e7)
    sefd_jy:float=Field(default=10000,gt=0,le=1e9)
    noise:bool=Field(default=False,strict=True)
    seed:int=Field(default=21,ge=0,le=2**32-1,strict=True)
    prior_fwhm_arcsec:float=Field(default=240,ge=40,le=500)
    entropy:float=Field(default=.01,ge=0,le=1)
    tsv:float=Field(default=.0001,ge=0,le=.01)
    starts:int=Field(default=3,ge=1,le=5,strict=True)
    max_iterations:int=Field(default=800,ge=100,le=2000,strict=True)

    @model_validator(mode='after')
    def dimensions(self):
        if self.duration_s%3: raise ValueError('観測時間は3秒の整数倍にしてください')
        return self


class AnalysisRequest(Request):
    kind:Literal['analysis']='analysis'
    manifest:str=Field(min_length=1,max_length=512)
    clock_model:str=Field(min_length=1,max_length=512)
    pilot_integrations:int=Field(default=256,ge=8,le=16384,strict=True)
    pilot_integration_s:float|None=Field(default=None,gt=0,le=3)
    start_offset_s:float=Field(default=.002,ge=0,le=86400)
    integration_s:Literal[.1,.3,1.,3.]=.3
    max_rate_hz:float=Field(default=100,gt=0,le=10000)
    prior_fwhm_arcsec:float=Field(default=240,ge=40,le=500)
    entropy:float=Field(default=.01,ge=0,le=1)
    tsv:float=Field(default=.0001,ge=0,le=.01)
    starts:int=Field(default=3,ge=1,le=5,strict=True)
    max_iterations:int=Field(default=800,ge=100,le=2000,strict=True)


class SynthesisRequest(Request):
    kind:Literal['synthesis']='synthesis'
    inputs:list[Annotated[str,Field(min_length=1,max_length=512)]]=Field(min_length=2,max_length=32)
    prior_fwhm_arcsec:float=Field(default=240,ge=40,le=500)
    entropy:float=Field(default=.01,ge=0,le=1)
    tsv:float=Field(default=.0001,ge=0,le=.01)
    starts:int=Field(default=3,ge=1,le=5,strict=True)
    max_iterations:int=Field(default=800,ge=100,le=2000,strict=True)


class SensitivityRequest(Request):
    kind:Literal['sensitivity']='sensitivity'
    antenna_mode:Literal['dish','effective']='dish'
    diameter_m:float=Field(default=1.,ge=.1,le=30.)
    aperture_efficiency:float=Field(default=.6,gt=0,le=1.)
    effective_area_m2:float=Field(default=.5,gt=0,le=10000.)
    system_temperature_k:float=Field(default=100.,ge=10.,le=10000.)
    integration_s:Literal[.1,.3,1.,3.]=.3
    bandwidth_hz:float=Field(default=256000.,gt=0,le=2048000.)
    stations:Literal[4,8]=8
    layout:Literal['spread','line','ring']='spread'
    flux_jy:float=Field(default=1000.,gt=0,le=1e7)


JobRequest=Annotated[SimulationRequest|ValidationRequest|RmlRequest|AnalysisRequest|SynthesisRequest|SensitivityRequest,Field(discriminator='kind')]
