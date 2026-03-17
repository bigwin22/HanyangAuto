# Hanyang LMS Video Flow Analysis

This document captures the verified login flow and reusable video lecture flow for `learning.hanyang.ac.kr`. It is intended to be reusable from future sessions when building or debugging browser automation across multiple courses, not just one course.

## Scope

- Verified against a real logged-in session on `2026-03-17`
- Focused on:
  - login / SSO handoff
  - cross-course lecture discovery
  - module-based video lecture discovery
  - playback behavior
  - progress refresh behavior
- Not focused on:
  - final full-completion threshold
  - long-duration playback until completion
  - PDF / quiz automation in this document

## High-Level Architecture

The LMS is not a single-layer app. The video lecture flow spans three systems:

1. `learning.hanyang.ac.kr`
   - Canvas-like LMS shell
   - dashboard, course cards, module routes, course navigation
2. `learningx`
   - course-specific learning / attendance LTI layer
   - lecture attendance item view, attendance state, lesson metadata
3. `hycms.hanyang.ac.kr`
   - actual video player / media delivery layer
   - playback UI, media streaming, playback statistics

For video lectures, the real flow is:

`Canvas course page -> Canvas module item -> learningx lecture_attendance view -> hycms video player`

## Login Flow

### Entry

- Start URL:
  - `https://learning.hanyang.ac.kr`

### Redirect

- The user is redirected to:
  - `https://api.hanyang.ac.kr/oauth/login`

### Login mechanics

The login page is not a plain HTML form submission.

- The page first requests:
  - `/oauth/public_token.json?t=mobile`
- Then the login script encrypts credentials client-side.
- Credentials are submitted to:
  - `/oauth/login_submit.json`

Observed behavior:

- success / redirect is controlled by response payload fields such as `code` and `url`
- after successful login, the user lands back on:
  - `https://learning.hanyang.ac.kr/`

### Important note

Automation should not assume a standard `<form>` POST. The login button triggers JavaScript logic, so robust automation should:

1. wait for `#uid`, `#upw`, `#login_btn`
2. fill the fields
3. click `#login_btn`
4. handle possible dialogs / alerts
5. wait until the LMS dashboard is visible

## Dashboard / Course Discovery

After login, the dashboard uses Canvas APIs.

Observed request:

- `GET /api/v1/dashboard/dashboard_cards`

Course cards contain URLs such as:

- `/courses/207438`
- `/courses/205006`

These `courseId` values are the base identifiers used throughout the rest of the system.

## Cross-Course Discovery Rule

After inspecting the dashboard courses and their Canvas module APIs, the most reusable discovery rule is:

- do not start from `external_tools/140`
- start from the Canvas modules API for each course
- identify lecture candidates as module items where:
  - `type = ExternalTool`
  - `content_id = 138`
  - or `external_url` contains `/learningx/lti/lecture_attendance/items/view/`

This pattern was observed repeatedly across multiple courses.

### Courses where this pattern was confirmed

Examples from the real session:

- `170463` `202510HY20289_CORE기초미적분`
  - many weekly items
  - all major lecture items were `ExternalTool(content_id=138)`
- `167987` `202510HY20290_CORE기초물리학`
  - many weekly lecture items
  - all major lecture items were `ExternalTool(content_id=138)`
- `205006` `202610HY25789_디지탈논리회로설계`
  - multiple weekly lecture items
  - all lecture items were `ExternalTool(content_id=138)`
- `206820` `202610HY24876_전자기학1`
  - lecture recordings were `ExternalTool(content_id=138)`
- `207438` `202610HY23329_IC-PBL과취창업을위한진로탐색`
  - lecture items were also `ExternalTool(content_id=138)`

### Course-level implication

The best generalized algorithm is:

1. discover dashboard courses
2. query `/api/v1/courses/{courseId}/modules?include[]=items&per_page=100`
3. collect candidate items where:
   - `item.type === "ExternalTool"`
   - `item.content_id === 138`
4. open each item through:
   - `item.html_url`
   - or directly the course module item route

This is more reliable than depending on the visible course navigation menu alone.

## Why `external_tools/140` Is Not Enough

In older or simpler automation logic, a common assumption is:

- course -> `external_tools/140` -> lecture list -> lecture item

That can be true for some courses, but it is not universal.

For the `IC-PBL과취창업을위한진로탐색` course:

- `external_tools/140` exists and is labeled `주차학습`
- but the rendered list showed `생성된 주차가 없습니다.`

However, the course still had video lectures.

Conclusion:

- do not rely on `external_tools/140` as the only source of lecture discovery
- some courses expose video lectures through Canvas modules instead
- even in courses that have a `주차학습` tab, the real playable lecture entries may still be better discovered from module items

## Verified Course: IC-PBL

### Course

- course title:
  - `202610HY23329_IC-PBL과취창업을위한진로탐색`
- course ID:
  - `207438`

### Canvas module API

This course exposes real video lecture entry points through Canvas modules.

Observed API:

- `GET /api/v1/courses/207438/modules?include[]=items&per_page=100`

Example module data:

- module name:
  - `2주차`
- item title:
  - `2026 진로탐색-2강 대학생사회진출환경변화와진로설계(1)`
- item type:
  - `ExternalTool`
- module item route:
  - `/courses/207438/modules/items/8454663`
- item external URL:
  - `https://learning.hanyang.ac.kr/learningx/lti/lecture_attendance/items/view/1028963`

### Important discovery rule

For this course, a video lecture can be identified by a module item with:

- `type = ExternalTool`
- `content_id = 138`
- `external_url` under:
  - `/learningx/lti/lecture_attendance/items/view/{itemId}`

This is a strong indicator that the item is a learning / attendance-managed lecture.

## Verified Video Lecture Example

### Canvas route

- `https://learning.hanyang.ac.kr/courses/207438/modules/items/8454663`

### learningx frame

Inside the page, Canvas renders a `tool_content` iframe whose URL is:

- `https://learning.hanyang.ac.kr/learningx/lti/lecture_attendance/items/view/1028963`

### hycms video frame

Inside the learningx lecture attendance view, the actual player loads another iframe:

- `https://hycms.hanyang.ac.kr/em/69af6d3d11db0?...`

This iframe is the real video player.

## What the learningx lecture page shows

The lecture attendance view displayed the following kinds of fields:

- learning 인정 period
  - start
  - due / deadline
  - close / end
- total playback time
- current learning progress
- completion status
- attendance status
- refresh button

Observed values for the example lecture:

- title:
  - `2026 진로탐색-2강 대학생사회진출환경변화와진로설계(1)`
- recognition period:
  - start: `3월 11일 오후 2:00`
  - due: `3월 18일 오후 2:00`
  - close: `3월 18일 오후 2:00`
- playback time:
  - `37분 3초`
- progress:
  - `1분 19초 (3.57%)`
- completion:
  - `미완료`
- attendance state:
  - `미결`

Visible button:

- `학습 상태 확인`

Visible warning:

- playback above `1.0x` may not count toward attendance

## Playback Rules Inferred from the Real Session

### Speed restriction

The page explicitly warns:

- only up to `1x` speed is safe for attendance recognition

The hycms player URL also contains:

- `mxpr=1.00`

This strongly suggests the backend / player integration is enforcing or at least tracking a maximum recognized playback rate of `1.0x`.

### Resume support

When playback was started, the player showed a resume dialog:

- `이전에 시청했던 01:19부터 이어서 보시겠습니까?`

Buttons:

- `예`
- `아니오`

So playback automation must handle resume prompts.

### Actual play start

After clicking play and then confirming resume:

- the player UI switched into an active playback state
- the player showed:
  - `일시정지`
  - `10초 이전`
  - `10초 이후`
  - `x 1.0`
- the time indicator showed:
  - `01:23 / 37:03`

This confirms the media was genuinely playing, not just opened.

## Verified Network Behavior During Playback

### Canvas page-level requests

Observed on module item open:

- `GET /api/v1/courses/207438/module_item_sequence?...`

### learningx lecture metadata

Observed when the lecture attendance view opened:

- `GET /learningx/api/v1/courses/207438/attendance_items/1028963`
- `GET /learningx/api/v1/courses/207438/settings?role=1`
- `GET /learningx/api/v1/courses/207438/lessons`

### Important session caveat

These `learningx` API calls succeeded when loaded as part of the real lecture page, but direct ad hoc fetches from the outer page or generic script contexts returned `401 Unauthorized`.

Conclusion:

- do not assume you can query `learningx` APIs freely from any page context
- they appear to depend on launch context, iframe/session state, and possibly extra headers or cookies

### hycms player requests

Observed during player startup:

- player config / skin / content metadata requests
- media file streaming:
  - `.../ssmovie.mp4` with `206 Partial Content`

This confirms actual video streaming started.

### Playback statistics request

After playback started, this request was observed:

- `POST https://hycms.hanyang.ac.kr/index.php?module=xn_viewer&act=procXn_viewerViewStatistics`

This indicates hycms records playback / view statistics independently.

### Progress target embedded in the player URL

The hycms iframe URL contained a `TargetUrl` parameter like:

- `https://learning.hanyang.ac.kr/learningx/api/v1/courses/207438/sections/0/components/1028963/progress?user_id=2025067192&content_id=69af6d3d11db0&content_type=movie`

This is a critical discovery.

It strongly implies:

1. the hycms player knows where to report progress
2. learning progress for the lecture is ultimately written to the `learningx` progress endpoint
3. the tracked entity is the `component`

For automation design, this is one of the most important facts discovered so far.

## What `학습 상태 확인` Actually Does

The `학습 상태 확인` button was clicked during the real session.

Observed result:

- it triggered another request to:
  - `/learningx/api/v1/courses/207438/attendance_items/1028963`

The displayed progress did not immediately change in the short test window, but the network behavior shows the button is used to:

- re-fetch server-side lecture attendance state
- synchronize the UI with the latest backend progress / attendance calculation

So the intended model is:

1. player records watch activity
2. backend updates progress
3. `학습 상태 확인` refreshes the current visible state

## Practical Automation Logic

For a robust automation flow on video lectures like this:

1. Log in through the SSO flow.
2. Discover the target course ID from the dashboard.
3. Prefer checking Canvas module items, not only `external_tools/140`.
4. Identify video lecture items by:
   - `type = ExternalTool`
   - `content_id = 138`
   - `external_url` containing `/learningx/lti/lecture_attendance/items/view/`
5. Open the module item route:
   - `/courses/{courseId}/modules/items/{moduleItemId}`
6. Wait for the `tool_content` iframe.
7. Inside `tool_content`, wait for the nested hycms iframe.
8. In the hycms frame:
   - click `재생`
   - if a resume dialog appears, choose a policy:
     - `예` to continue previous progress
     - `아니오` to start over
9. Keep playback at `1.0x`.
10. Wait long enough for meaningful progress to be reported.
11. Back in the learningx frame, click `학습 상태 확인`.
12. Read:
   - progress text
   - completion state
   - attendance state

## Important Caveats

### 1. Do not treat short playback as immediate progress update

In the test session, a short playback interval did not immediately change:

- `1분 19초 (3.57%)`
- `미완료`
- `미결`

Possible reasons:

- server sync interval
- minimum reporting threshold
- progress batching
- delayed attendance recalculation

### 2. `external_tools/140` is not universal

Some courses expose lectures there.
This IC-PBL course did not expose the real video entries there.

### 3. learningx APIs are context-sensitive

Direct manual fetches often returned `401`, even though the page itself loaded them successfully.

### 4. Some assets 404 but playback still works

Several hycms support files returned `404`, such as:

- `chapter.xml`
- `media_script_list.xml`
- some skin CSS / caption files

Playback still started, so these are not necessarily fatal.

## Reliable Selectors / Patterns Observed

These were verified during the session.

### Login page

- ID input:
  - `#uid`
- password input:
  - `#upw`
- login button:
  - `#login_btn`

### learningx lecture page

- outer lecture frame:
  - `iframe[name="tool_content"]`
- visible progress refresh button text:
  - `학습 상태 확인`

### hycms player

- initial play button text:
  - `재생`
- resume prompt buttons:
  - `예`
  - `아니오`
- active playback controls:
  - `일시정지`
  - `10초 이전`
  - `10초 이후`
  - `x 1.0`

## What Is Known vs Unknown

### Known

- the full login path
- the Canvas dashboard discovery path
- that IC-PBL video lectures live in Canvas modules
- the exact module item used for a real lecture
- the learningx lecture attendance frame URL pattern
- the hycms player URL pattern
- that playback produces real media streaming
- that playback produces hycms statistics events
- that the player URL embeds a learningx progress target
- that `학습 상태 확인` refreshes attendance item state

### Still unknown

- exact server rule for when `미완료 -> 완료`
- exact server rule for when `미결 -> 출석/인정`
- whether there is a minimum watch threshold before a progress refresh becomes visible
- whether progress is flushed on a timer, on pause, on exit, or on periodic checkpoints

## Recommendation for Future Automation Work

If the goal is a reliable auto-watch program, future implementation should be based on:

- real Canvas module discovery
- real `learningx` lecture attendance pages
- real nested hycms playback control
- explicit handling for:
  - resume prompts
  - 1.0x playback
  - delayed progress refresh
- repeated `학습 상태 확인` checks

### Recommended generalized discovery priority

For all-course automation, use this priority order:

1. Canvas modules API
   - `/api/v1/courses/{courseId}/modules?include[]=items&per_page=100`
   - prefer `ExternalTool(content_id=138)`
2. fallback course navigation tabs
   - especially when module APIs are empty or unusual
3. fallback visible `external_tools/140` lecture lists
   - only when course content is actually exposed there

### Why this priority is recommended

- It worked across multiple different courses in the real session.
- It captures both “standard lecture recording” style courses and special cases like IC-PBL.
- It gives stable machine-readable metadata:
  - module name
  - item title
  - `item.html_url`
  - `item.external_url`
  - `content_id`

The next most valuable experiment would be:

1. open this same IC-PBL lecture
2. play for a longer interval, such as 2 to 5 minutes
3. click `학습 상태 확인`
4. compare:
   - progress percent
   - completion state
   - attendance state
   - any additional progress-related network calls

That would likely reveal the first visible update threshold and clarify how often the backend commits watch progress.
