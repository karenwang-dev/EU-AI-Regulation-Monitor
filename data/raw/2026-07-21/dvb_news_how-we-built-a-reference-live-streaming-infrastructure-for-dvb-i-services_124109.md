[![](https://dvb.org/wp-content/uploads/2026/06/202606_live-linear-test-streams_1280x720-1024x576.png)](https://dvb.org/wp-content/uploads/2026/06/202606_live-linear-test-streams_1280x720.png)

# How we built a reference live streaming infrastructure for DVB-I services

24.06.2026


* * *

_Juha Joki (Sofia Digital) and Romain Bouqueau (Motion Spell)_

As DVB-I deployments mature, the industry faces a challenge: the lack of consistently available, high-quality reference live streams for testing and validation. Implementers need reliable test content spanning multiple codecs and configurations to verify their solutions against [DVB-DASH](https://dvb.org/?standard=dvb-mpeg-dash-profile-for-transport-of-iso-bmff-based-dvb-services-over-ip-based-networks) – the DVB profile of MPEG-DASH for IPTV and streaming services – and related specifications. Recognizing this gap, the DVB Project chose Sofia Digital, in partnership with Motion Spell and Télécom Paris, home of the GPAC project, to establish and support a [comprehensive live-linear streaming infrastructure that serves as a DVB community reference implementation](https://dvb.org/specifications/verification-validation/dvb-live-linear-test-streams/).

## Implementation approach

The project leverages two complementary open-source streaming solutions, based on livesim2 and GPAC. [livesim2](https://livesim.dashif.org/), already used in the HbbTV DASH DRM Reference Application, is a specialized DASH live streaming simulator. [GPAC](https://gpac.io/) is an open-source multimedia framework providing packaging, multiplexing and delivery tools. With its 25-year history and adoption by organizations including Netflix and multiple standards bodies, it brings this reference implementation one step closer to actual deployments.

Both solutions are documented with step-by-step installation guides for all major platforms.

The technical implementation encompasses a range of codecs reflecting current and emerging broadcast standards. Video encoding starts from AVC (H.264) and HEVC (H.265) through to VVC (H.266) and AVS3, with HDR variants HLG and PQ10. For audio, there’s AAC for broad compatibility, with advanced codecs such as MPEG-H and Dolby AC-4, which support immersive and accessible audio scenarios. Stream generation uses industry-standard tools including FFmpeg, uavs3e, GPAC’s MP4Box, and Fraunhofer’s MPEG-H Authoring Tool.

All streams underwent a triple-fold validation: conformance checking via the new version of the DASH-IF conformance tool, playback verification across multiple device platforms and players, and a verification script modeled after CTA-WAVE test methodologies.

![](https://dvb.org/wp-content/uploads/2026/06/live-linear-streams-1024x605.png)

## Supported deliverables

The infrastructure provides nine distinct 24/7 live-linear streams, each targeting specific test scenarios, from basic AVC-HD with subtitles through UHD content with advanced audio and HDR. These streams are hosted on EU-based infrastructure (Hetzner) with guaranteed availability, and with enhanced support during major industry events like IBC and DVB World.

DVB-I service lists are generated using a management tool from Sofia Digital, offering implementers ready-to-use configurations and a basis for manual customization. Documentation enables organizations to deploy streaming setups locally, supporting both cloud-based testing against the shared reference and private development environments.

The diversity of the open-source streaming ecosystem reflects the technological potential for DVB technologies. The DASH-IF livesim2 simulator is now complemented by GPAC’s _jitsu_, a just-in-time packager that brings GPAC’s maturity, extensive codec support and broad industry deployment to the service of the DVB community.

This project extends support for the DVB-I reference infrastructure, offering both continuity and choice for tests and deployments.

## Future directions

The project laid out robust foundations. Future phases could include more codec variants, more industry use cases, and enhanced features including DRM integration and advertisement insertion capabilities. The modular architecture and proper documentation ensure the infrastructure can evolve alongside DVB specification development and industry needs.

This reference infrastructure represents a collaborative investment in the DVB-I ecosystem, providing implementers with the reliable, professionally maintained test resources that are essential for bringing robust solutions to market.

_To access the live streams visit: [https://live-linear.dvb.org](https://live-linear.dvb.org/), also available via the [Verification and Validation (V&V)](https://dvb.org/specifications/verification-validation/) page on the DVB website._ _This article first appeared in Issue 67 of [DVB Scene](https://dvb.org/dvb-scene/) magazine._

* * *

**Juha Joki** is Director of Broadcast and Testing at [Sofia Digital](https://sofiadigital.com/), with over 15 years’ experience delivering end-to-end DVB, DVB-I and streaming solutions.

**Romain Bouqueau** is founder and CEO of [Motion Spell](https://www.motionspell.com/) and a key GPAC contributor advancing open standards and open-source innovation.

This website uses cookies to improve your experience. We'll assume you're ok with this, but you can opt-out if you wish. Cookie settingsACCEPT

Privacy & Cookies Policy

Close

#### Privacy Overview

This website uses cookies to improve your experience while you navigate through the website. Out of these cookies, the cookies that are categorized as necessary are stored on your browser as they are essential for the working of basic functionalities...

Necessary

Necessary

Always Enabled

Necessary cookies are absolutely essential for the website to function properly. This category only includes cookies that ensures basic functionalities and security features of the website. These cookies do not store any personal information.

Functional

Functional

Functional cookies help to perform certain functionalities like sharing the content of the website on social media platforms, collect feedbacks, and other third-party features.


Performance

Performance

Performance cookies are used to understand and analyze the key performance indexes of the website which helps in delivering a better user experience for the visitors.


Analytics

Analytics

Analytical cookies are used to understand how visitors interact with the website. These cookies help provide information on metrics the number of visitors, bounce rate, traffic source, etc.

| Cookie | Duration | Description |
| --- | --- | --- |
| CONSENT | 2 years | YouTube sets this cookie via embedded YouTube videos and registers anonymous statistical data. |

Advertisement

Advertisement

Advertisement cookies are used to provide visitors with relevant ads and marketing campaigns. These cookies track visitors across websites and collect information to provide customized ads.

| Cookie | Duration | Description |
| --- | --- | --- |
| VISITOR\_INFO1\_LIVE | 5 months 27 days | YouTube sets this cookie to measure bandwidth, determining whether the user gets the new or old player interface. |
| YSC | session | Youtube sets this cookie to track the views of embedded videos on Youtube pages. |
| yt-remote-connected-devices | never | YouTube sets this cookie to store the user's video preferences using embedded YouTube videos. |
| yt-remote-device-id | never | YouTube sets this cookie to store the user's video preferences using embedded YouTube videos. |
| yt.innertube::nextId | never | YouTube sets this cookie to register a unique ID to store data on what videos from YouTube the user has seen. |
| yt.innertube::requests | never | YouTube sets this cookie to register a unique ID to store data on what videos from YouTube the user has seen. |

Others

Others

Other uncategorized cookies are those that are being analyzed and have not been classified into a category as yet.

| Cookie | Duration | Description |
| --- | --- | --- |
| VISITOR\_PRIVACY\_METADATA | 5 months 27 days | Description is currently not available. |

SAVE & ACCEPT

Powered by [![CookieYes Logo](https://dvb.org/wp-content/plugins/cookie-law-info/legacy/public/images/logo-cookieyes.svg)](https://www.cookieyes.com/)

reCAPTCHA

Recaptcha requires verification.

protected by **reCAPTCHA**