#pragma D option quiet
#pragma D option strsize=128
#pragma D option bufsize=2m
#pragma D option switchrate=20hz
/* Private offsets require AMD CA0F82D9 and HWLibs AF4BC84B.
   Tail-jump FBT return events are intentionally excluded. */
BEGIN { printf("TRACE_READY wall=%Y ns=%lld\n",walltimestamp,(long long)timestamp); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine5startEv:entry
{
    printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_START pid=%d started=%u firmware_loaded=%u refs=%u\n",pid,*(uint8_t*)(arg0+0x10),*(uint8_t*)(arg0+0x13d),*(uint32_t*)(arg0+0x138));
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine5startEv:return
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_START_RESULT pid=%d bool=%u\n",pid,(uint8_t)arg1); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine4stopEv:entry
{
    self->stop_engine=arg0;
    printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_STOP_ENTER pid=%d started=%u refs=%u\n",pid,*(uint8_t*)(arg0+0x10),*(uint32_t*)(arg0+0x138));
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine4stopEv:return
/self->stop_engine/
{
    printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_STOP_RESULT pid=%d bool=%u started=%u refs=%u\n",pid,(uint8_t)arg1,*(uint8_t*)(self->stop_engine+0x10),*(uint32_t*)(self->stop_engine+0x138));
    self->stop_engine=0;
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine19releaseHardwareCailEv:entry
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_RELEASE_CAIL_ENTER pid=%d\n",pid); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine19releaseHardwareCailEv:return
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_RELEASE_CAIL_RESULT pid=%d bool=%u\n",pid,(uint8_t)arg1); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine16initHardwareCailEb:return
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_INIT_CAIL_RESULT pid=%d bool=%u\n",pid,(uint8_t)arg1); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine21setSuspendResumeStateEb:entry
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("VCE_POWER_STATE pid=%d argument=%u started=%u\n",pid,(uint8_t)arg1,*(uint8_t*)(arg0+0x10)); }
fbt:com.apple.kext.AMDRadeonX5000:_ZN36AMDRadeonX5000_AMDVega10VideoContext11startEngine*:entry
/arg1 && arg2 == 12/
{
    self->channel=*(uint32_t*)(arg1+8);
    printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("KERNEL_START pid=%d channel=%u size=%ld\n",pid,self->channel,arg2);
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN36AMDRadeonX5000_AMDVega10VideoContext11startEngine*:return
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("KERNEL_START_RESULT pid=%d channel=%u status=0x%x\n",pid,self->channel,(uint32_t)arg1); }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CAILVceControl:entry
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("CAIL_VCE pid=%d op=%d initialized=%u\n",pid,arg1,(*(uint8_t*)(arg0+0xe49)&0x10)!=0); }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceLoadEngine:entry
{ self->loadctx=arg0;printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("LOAD_ENTER pid=%d flag=0x%x\n",pid,*(uint8_t*)(arg0+0xe49)); }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceLoadEngine:return
/self->loadctx/
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("LOAD_RESULT pid=%d status=%u flag=0x%x\n",pid,(uint32_t)arg1,*(uint8_t*)(self->loadctx+0xe49));self->loadctx=0; }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceInit:entry
{
    self->initctx=arg0;
    printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("INIT_ENTER pid=%d context=%p flags=0x%x size=0x%x\n",pid,arg0,*(uint8_t*)(arg0+0xe49),arg1?*(uint32_t*)arg1:0);
    stack(12);
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceInit:return
/self->initctx/
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("INIT_RESULT pid=%d status=%u flags=0x%x\n",pid,(uint32_t)arg1,*(uint8_t*)(self->initctx+0xe49));self->initctx=0; }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceSuspend:entry
{ self->suspendctx=arg0;printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("SUSPEND_ENTER pid=%d context=%p flags=0x%x\n",pid,arg0,*(uint8_t*)(arg0+0xe49));stack(12); }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceSuspend:return
/self->suspendctx/
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("SUSPEND_RESULT pid=%d status=%u flags=0x%x\n",pid,(uint32_t)arg1,*(uint8_t*)(self->suspendctx+0xe49));self->suspendctx=0; }
fbt:com.apple.kext.AMDRadeonX5000HWLibs:greenland_vce_init:entry,
fbt:com.apple.kext.AMDRadeonX5000HWLibs:vce_init:entry,
fbt:com.apple.kext.AMDRadeonX5000HWLibs:Cail_Powerup:entry,
fbt:com.apple.kext.AMDRadeonX5000HWLibs:Cail_Powerdown:entry
{ printf("ns=%lld tid=%d ",(long long)timestamp,tid);printf("HARDWARE_PATH fn=%s pid=%d\n",probefunc,pid); }
tick-600sec { printf("TRACE_HARD_DEADLINE\n");exit(0); }
END { printf("TRACE_END wall=%Y\n",walltimestamp); }
