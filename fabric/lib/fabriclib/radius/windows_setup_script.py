import base64
import hashlib

from fabriclib.radius.windows_lan_profile import windows_lan_profile

_HEAD = r"""<#
  fabric 802.1X setup for {domain}: {what}.
  Run once, in PowerShell as Administrator:
      powershell -ExecutionPolicy Bypass -File .\{filename}{usage}
  -Interface: the wired adapter's name (Get-NetAdapter), default "Ethernet".
  Made by fabric for this network; untested on Windows by the fabric project
  until the hardware test.
#>
param(
    [string]$Interface = "Ethernet"{params}
)
$ErrorActionPreference = "Stop"
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    throw "Run this in PowerShell opened with 'Run as administrator'."
}}
Get-NetAdapter -Name $Interface | Out-Null     # stops here if there is no such adapter

# 1. Wired 802.1X runs in the Wired AutoConfig service (dot3svc), off by default.
Set-Service -Name dot3svc -StartupType Automatic
Start-Service -Name dot3svc

# 2. Trust the fabric root CA: Windows checks that the server is {server} from it.
$ca = Join-Path $env:TEMP "fabric-root-ca.crt"
Set-Content -Path $ca -Encoding Ascii -Value @'
{root_pem}
'@
Import-Certificate -FilePath $ca -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Remove-Item $ca
"""
_TLS_CERT = r"""
# 3. This device's certificate (.p12 from the Step-CA tab, issued for this device),
#    into the computer's store: the port opens before anyone signs in.
$password = Read-Host -AsSecureString "Password of $Pfx"
Import-PfxCertificate -FilePath $Pfx -CertStoreLocation Cert:\LocalMachine\My -Password $password | Out-Null
"""
_PROFILE = r"""
# {step}. The 802.1X profile on the wired adapter.
$xml = Join-Path $env:TEMP "fabric-8021x.xml"
Set-Content -Path $xml -Encoding Ascii -Value @'
{profile}'@
netsh lan add profile filename="$xml" interface="$Interface"
Remove-Item $xml
netsh lan reconnect interface="$Interface"
Write-Host "Done. {done}"
Write-Host "Check: netsh lan show interfaces   (and Recent decisions on the FreeRADIUS tab)"
"""


def windows_setup_script(v, method, root_pem):
    """A PowerShell script that sets a Windows PC up for 802.1X on this
    fabric: Wired AutoConfig on, the fabric root CA (`root_pem`) trusted, for
    "tls" the device's .p12 imported into the computer store, and the wired
    profile (windows_lan_profile) added. Only public data goes in it.
    Returns (file name, script with CRLF line ends)."""
    pem = root_pem.replace("\r", "").strip()
    der = base64.b64decode("".join(line for line in pem.splitlines() if "-----" not in line))
    sha1 = hashlib.sha1(der).hexdigest()
    thumb = " ".join(sha1[i:i + 2] for i in range(0, 40, 2))
    server, domain = v.get("hostname_radius", ""), v.get("domain", "")
    filename = f"fabric-8021x-{method}.ps1"
    if method == "tls":
        head = _HEAD.format(domain=domain, what="this device joins with its certificate (EAP-TLS)",
                            filename=filename, usage=" -Pfx .\\<device>.p12",
                            params=",\n    [Parameter(Mandatory = $true)][string]$Pfx", server=server, root_pem=pem)
        body = _TLS_CERT + _PROFILE.format(step=4, profile=windows_lan_profile("tls", server, thumb),
                                           done="The port opens with this device's certificate.")
    elif method == "ttls":
        head = _HEAD.format(domain=domain, what="people sign in with their user name and password (EAP-TTLS)",
                            filename=filename, usage="", params="", server=server, root_pem=pem)
        body = _PROFILE.format(step=3, profile=windows_lan_profile("ttls", server, thumb),
                               done="Windows asks for the user name and password when the cable is plugged in.")
    else:
        raise ValueError(f"unknown method {method!r}")
    return filename, (head + body).replace("\n", "\r\n")
