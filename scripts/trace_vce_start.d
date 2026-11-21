#pragma D option quiet
#pragma D option strsize=128
/* Offsets apply only to AMD CA0F82D9 and HWLibs AF4BC84B on 24H232.
   Do not use FBT tail-jump return values as actual CAIL status codes. */
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine5startEv:entry
{
    printf("VCE_START pid=%d started=%u firmware_loaded=%u\n",pid,*(uint8_t*)(arg0+0x10),*(uint8_t*)(arg0+0x13d));
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine5startEv:return
{
    printf("VCE_START_RESULT pid=%d bool=%u\n",pid,(uint8_t)arg1);
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine4stopEv:entry
{
    printf("VCE_STOP pid=%d started=%u refs=%u\n",pid,*(uint8_t*)(arg0+0x10),*(uint32_t*)(arg0+0x138));
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine19releaseHardwareCailEv:entry
{
    printf("VCE_RELEASE_CAIL pid=%d\n",pid);
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN29AMDRadeonX5000_AMDVCEHWEngine16initHardwareCailEb:return
{
    printf("VCE_INIT_CAIL_RESULT bool=%u\n",(uint8_t)arg1);
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN36AMDRadeonX5000_AMDVega10VideoContext11startEngine*:entry
{
    self->channel=*(uint32_t*)(arg1+8);
    printf("KERNEL_START pid=%d channel=%u size=%ld\n",pid,self->channel,arg2);
}
fbt:com.apple.kext.AMDRadeonX5000:_ZN36AMDRadeonX5000_AMDVega10VideoContext11startEngine*:return
{
    printf("KERNEL_START_RESULT pid=%d channel=%u status=0x%x\n",pid,self->channel,(uint32_t)arg1);
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CAILVceControl:entry
{
    printf("CAIL_VCE op=%d initialized=%u\n",arg1,(*(uint8_t*)(arg0+0xe49)&0x10)!=0);
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceLoadEngine:entry
{
    self->loadctx=arg0;printf("LOAD_ENTER flag=0x%x\n",*(uint8_t*)(arg0+0xe49));
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceLoadEngine:return
{
    printf("LOAD_RESULT status=%u flag=0x%x\n",(uint32_t)arg1,*(uint8_t*)(self->loadctx+0xe49));
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceInit:entry
{
    self->initctx=arg0;printf("INIT_ENTER flags=0x%x size=0x%x\n",*(uint8_t*)(arg0+0xe49),*(uint32_t*)arg1);
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceInit:return
{
    printf("INIT_RESULT status=%u flags=0x%x\n",(uint32_t)arg1,*(uint8_t*)(self->initctx+0xe49));
}
fbt:com.apple.kext.AMDRadeonX5000HWLibs:CailVceSuspend:entry,
fbt:com.apple.kext.AMDRadeonX5000HWLibs:greenland_vce_init:entry,
fbt:com.apple.kext.AMDRadeonX5000HWLibs:vce_init:entry
{
    printf("HARDWARE_PATH fn=%s pid=%d\n",probefunc,pid);
}
tick-20sec {exit(0);}
