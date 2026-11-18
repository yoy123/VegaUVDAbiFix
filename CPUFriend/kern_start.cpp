//
//  kern_start.cpp
//  CPUFriend
//
//  Copyright © 2017-2022 PMheart. All rights reserved.
//

#include <Headers/plugin_start.hpp>
#include <Headers/kern_api.hpp>

#include "CPUFriend.hpp"

static CPUFriendPlugin cpuf;

static const char *bootargOff[] {
	"-vegauvdoff"
};

static const char *bootargDebug[] {
	"-vegauvddebug"
};

static const char *bootargBeta[] {
	"-vegauvdbeta"
};

PluginConfiguration ADDPR(config) {
	xStringify(PRODUCT_NAME),
	parseModuleVersion(xStringify(MODULE_VERSION)),
	LiluAPI::AllowNormal,
	bootargOff,
	arrsize(bootargOff),
	bootargDebug,
	arrsize(bootargDebug),
	bootargBeta,
	arrsize(bootargBeta),
	KernelVersion::Sequoia,
	KernelVersion::Sequoia,
	[]() {
		cpuf.init();
	}
};
