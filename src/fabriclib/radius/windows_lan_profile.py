from xml.sax.saxutils import escape

# Windows wired (LAN) profile with the EapHost schemas (EAP-TLS: type 13;
# EAP-TTLS: type 21, Microsoft's method, author 311). Untested on Windows by
# the fabric project until the hardware test (see the FreeRADIUS tab).
_TTLS = """<Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
          <EapTtls xmlns="http://www.microsoft.com/provisioning/EapTtlsConnectionPropertiesV1">
            <ServerValidation>
              <ServerNames>{server}</ServerNames>
              <TrustedRootCAHash>{thumb}</TrustedRootCAHash>
              <DisablePrompt>true</DisablePrompt>
            </ServerValidation>
            <Phase2Authentication>
              <PAPAuthentication />
            </Phase2Authentication>
            <Phase1Identity>
              <IdentityPrivacy>true</IdentityPrivacy>
              <AnonymousIdentity>anonymous</AnonymousIdentity>
            </Phase1Identity>
          </EapTtls>
        </Config>"""
_TLS = """<Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
          <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1">
            <Type>13</Type>
            <EapType xmlns="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV1">
              <CredentialsSource>
                <CertificateStore>
                  <SimpleCertSelection>true</SimpleCertSelection>
                </CertificateStore>
              </CredentialsSource>
              <ServerValidation>
                <DisableUserPromptForServerValidation>true</DisableUserPromptForServerValidation>
                <ServerNames>{server}</ServerNames>
                <TrustedRootCA>{thumb}</TrustedRootCA>
              </ServerValidation>
              <DifferentUsername>false</DifferentUsername>
              <PerformServerValidation xmlns="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">true</PerformServerValidation>
              <AcceptServerName xmlns="http://www.microsoft.com/provisioning/EapTlsConnectionPropertiesV2">true</AcceptServerName>
            </EapType>
          </Eap>
        </Config>"""
_PROFILE = """<?xml version="1.0"?>
<LANProfile xmlns="http://www.microsoft.com/networking/LAN/profile/v1">
  <MSM>
    <security>
      <OneXEnforced>false</OneXEnforced>
      <OneXEnabled>true</OneXEnabled>
      <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
        <cacheUserData>true</cacheUserData>
        <authMode>{mode}</authMode>
        <EAPConfig>
      <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
        <EapMethod>
          <Type xmlns="http://www.microsoft.com/provisioning/EapCommon">{eap_type}</Type>
          <VendorId xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorId>
          <VendorType xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorType>
          <AuthorId xmlns="http://www.microsoft.com/provisioning/EapCommon">{author}</AuthorId>
        </EapMethod>
        {config}
      </EapHostConfig>
        </EAPConfig>
      </OneX>
    </security>
  </MSM>
</LANProfile>
"""


def windows_lan_profile(method, server_name, root_sha1):
    """Purpose: The wired 802.1X profile Windows imports (`netsh lan add profile`).
    Inputs:  method — "tls" (the machine's certificate, before anyone signs in) or "ttls" (the person's user name and
             password, PAP inside TLS).
             server_name — str the server certificate must name.
             root_sha1 — the root CA's SHA-1 thumbprint ("aa bb cc …"). Both are XML-escaped.
    Returns: the LANProfile XML (str).
    Fails:   ValueError "unknown method …".
    Feeds:   windows_setup_script.
    Notes:   either way Windows checks the server name and root CA without asking the user. Untested on Windows by the
             fabric project until the hardware test.
    """
    thumb, server = escape(root_sha1), escape(server_name)
    if method == "tls":
        config, mode, eap_type, author = _TLS.format(server=server, thumb=thumb), "machine", 13, 0
    elif method == "ttls":
        config, mode, eap_type, author = _TTLS.format(server=server, thumb=thumb), "user", 21, 311
    else:
        raise ValueError(f"unknown method {method!r}")
    return _PROFILE.format(mode=mode, eap_type=eap_type, author=author, config=config)
