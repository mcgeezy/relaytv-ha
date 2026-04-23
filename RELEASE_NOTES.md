# RelayTV HA 0.3.12

## HACS Install Layout Fix

This release fixes the HACS `relaytv.zip` package layout. Version `0.3.11` packaged the integration inside an extra top-level `relaytv/` directory, which could install as:

```text
/config/custom_components/relaytv/relaytv/manifest.json
```

Home Assistant expects:

```text
/config/custom_components/relaytv/manifest.json
```

Updating to `0.3.12` restores the correct flat zip layout for HACS installs and updates. Restart Home Assistant after updating.

## Companion App Share Automation

This release continues to highlight the Home Assistant Companion App share automation flow. You can share URLs or text from the Home Assistant mobile app and send them directly to RelayTV with `relaytv.smart_url`.

```yaml
alias: RelayTV - Smart play from share
description: Opens shared URLs/text in RelayTV via relaytv.smart_url
triggers:
  - event_type: mobile_app.share
    trigger: event
conditions:
  - condition: template
    value_template: "{{ shared | trim | length > 0 }}"
actions:
  - data:
      url: "{{ shared | trim }}"
    action: relaytv.smart_url
mode: single
variables:
  shared: |-
    {{ trigger.event.data.url
       if trigger.event.data.url is defined else
       (trigger.event.data.text if trigger.event.data.text is defined else '') }}
```

## HACS Display Assets

- Keeps integration brand assets under `custom_components/relaytv/brand/`.
- Keeps root-level `icon.png` and `logo.png` fallbacks for repository/HACS renderers that look at the repository root.
- Uses the README screenshot hosted from GitHub raw content for reliable rendering in HACS.

Note: HACS' integration list icon is ultimately loaded from `brands.home-assistant.io` for integration domains. If the RelayTV icon still appears generic in the list, the remaining durable step is submitting `relaytv` to the Home Assistant Brands repository.
