#!/usr/bin/env python
#######################################################################
## Copyright (c) 2017 VMware, Inc. All Rights Reserved.
## SPDX-License-Identifier: Apache-2.0
#######################################################################

"""
Sample function to list virtual machines in vSphere inventory.

** REQUIREMENTS **

* secret

cat << EOF > vsphere.json
{
    "password": "VSPHERE_PASSWORD",
    "username": "VSPHERE_USERNAME"
}
EOF
dispatch create secret vsphere vsphere.json

* image
dispatch create base-image python-vmomi kars7e/dispatch-openfaas-python3-vmomi:0.0.2-dev1 --language python3 --public
vs create image python-vmomi python-vmomi

Create a function:
dispatch create function python-vmomi getvms examples/python3/getvms.py --secret vsphere

Execute it:
dispatch exec getvms --wait --input='{"host": "VSPHERE_URL"}' --secret vsphere

"""

from __future__ import print_function

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

import ssl


def PrintVmInfo(vm, depth=1, info=None):
    """
    Print information for a particular virtual machine or recurse into a folder
    or vApp with depth protection
    """
    maxdepth = 10
    if info is None:
        info = []

    # if this is a group it will have children. if it does, recurse into them
    # and then return
    if hasattr(vm, 'childEntity'):
        if depth > maxdepth:
            return info
        vmList = vm.childEntity
        for c in vmList:

            info = PrintVmInfo(c, depth+1, info)
        return info

    # if this is a vApp, it likely contains child VMs
    # (vApps can nest vApps, but it is hardly a common usecase, so ignore that)
    if isinstance(vm, vim.VirtualApp):
        vmList = vm.vm
        for c in vmList:
            info = PrintVmInfo(c, depth+1, info)
        return

    summary = vm.summary
    vminfo = {
        "name": summary.config.name,
        "path": summary.config.vmPathName,
        "guest": summary.config.guestFullName,
        "state": summary.runtime.powerState
    }
    annotation = summary.config.annotation
    if annotation != None and annotation != "":
        vminfo["annotation"] = annotation
    if summary.guest != None:
        ip = summary.guest.ipAddress
        if ip != None and ip != "":
            vminfo["ip"] = ip
    if summary.runtime.question != None:
        vminfo["question"] = summary.runtime.question.text
    info.append(vminfo)
    return info

def handle(ctx, payload):
    host = payload.get("host")
    port = payload.get("port", 443)
    if host is None:
        raise Exception("Host required")
    secrets = ctx["secrets"]
    if secrets is None:
        raise Exception("Requires vsphere secrets")
    username = secrets["username"]
    password = secrets.get("password", "")
    context = None
    if hasattr(ssl, '_create_unverified_context'):
        context = ssl._create_unverified_context()
    si = SmartConnect(host=host,
                        user=username,
                        pwd=password,
                        port=port,
                        sslContext=context)
    if not si:
        raise Exception(
            "Could not connect to the specified host using specified "
            "username and password")
    try:
        content = si.RetrieveContent()
        info = []
        for child in content.rootFolder.childEntity:
            if hasattr(child, 'vmFolder'):
                datacenter = child
                vmFolder = datacenter.vmFolder
                vmList = vmFolder.childEntity
                for vm in vmList:
                    info.extend(PrintVmInfo(vm))
        return info
    finally:
        Disconnect(si)


