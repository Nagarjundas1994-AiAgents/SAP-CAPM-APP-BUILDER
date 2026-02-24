# SAP Fiori Elements Reference

Configuration patterns for Fiori Elements V4 applications.

## manifest.json Structure

```json
{
  "_version": "1.59.0",
  "sap.app": {
    "id": "com.company.myapp",
    "type": "application",
    "title": "My Application",
    "description": "Application description",
    "applicationVersion": { "version": "1.0.0" },
    "dataSources": {
      "mainService": {
        "uri": "/odata/v4/my-service/",
        "type": "OData",
        "settings": { "odataVersion": "4.0" }
      }
    },
    "crossNavigation": {
      "inbounds": {
        "myapp-display": {
          "semanticObject": "MyApp",
          "action": "display",
          "title": "My Application",
          "signature": { "parameters": {}, "additionalParameters": "allowed" }
        }
      }
    }
  },
  "sap.ui5": {
    "flexEnabled": true,
    "dependencies": {
      "minUI5Version": "1.120.0",
      "libs": { "sap.fe.templates": {} }
    },
    "models": {
      "": {
        "dataSource": "mainService",
        "preload": true,
        "settings": {
          "synchronizationMode": "None",
          "operationMode": "Server",
          "autoExpandSelect": true,
          "earlyRequests": true
        }
      },
      "i18n": {
        "type": "sap.ui.model.resource.ResourceModel",
        "settings": { "bundleName": "com.company.myapp.i18n.i18n" }
      }
    },
    "routing": {
      "routes": [
        {
          "pattern": ":?query:",
          "name": "OrdersList",
          "target": "OrdersList"
        },
        {
          "pattern": "Orders({key}):?query:",
          "name": "OrdersObjectPage",
          "target": "OrdersObjectPage"
        },
        {
          "pattern": "Orders({key})/items({key2}):?query:",
          "name": "OrderItemsObjectPage",
          "target": "OrderItemsObjectPage"
        }
      ],
      "targets": {
        "OrdersList": {
          "type": "Component",
          "id": "OrdersList",
          "name": "sap.fe.templates.ListReport",
          "options": {
            "settings": {
              "contextPath": "/Orders",
              "variantManagement": "Page",
              "initialLoad": "Enabled",
              "controlConfiguration": {
                "@com.sap.vocabularies.UI.v1.LineItem": {
                  "tableSettings": {
                    "type": "ResponsiveTable",
                    "enableExport": true,
                    "selectionMode": "Multi"
                  }
                }
              }
            }
          }
        },
        "OrdersObjectPage": {
          "type": "Component",
          "id": "OrdersObjectPage",
          "name": "sap.fe.templates.ObjectPage",
          "options": {
            "settings": {
              "contextPath": "/Orders",
              "editableHeaderContent": false,
              "controlConfiguration": {}
            }
          }
        },
        "OrderItemsObjectPage": {
          "type": "Component",
          "id": "OrderItemsObjectPage",
          "name": "sap.fe.templates.ObjectPage",
          "options": {
            "settings": {
              "contextPath": "/Orders/items"
            }
          }
        }
      }
    }
  },
  "sap.cloud": {
    "public": true,
    "service": "com.company.myapp"
  }
}
```

## Flexible Column Layout (FCL)

Add to manifest.json `sap.ui5.routing`:

```json
{
  "config": {
    "flexibleColumnLayout": {
      "defaultTwoColumnLayoutType": "TwoColumnsMidExpanded",
      "defaultThreeColumnLayoutType": "ThreeColumnsMidExpanded"
    }
  }
}
```

## Component.js

```javascript
sap.ui.define(["sap/fe/core/AppComponent"], function (AppComponent) {
  "use strict";
  return AppComponent.extend("com.company.myapp.Component", {
    metadata: { manifest: "json" },
  });
});
```

## xs-app.json (Managed App Router)

```json
{
  "welcomeFile": "/index.html",
  "authenticationMethod": "route",
  "routes": [
    {
      "source": "^/odata/v4/(.*)$",
      "target": "/odata/v4/$1",
      "destination": "srv-api",
      "authenticationType": "xsuaa",
      "csrfProtection": false
    },
    {
      "source": "^(.*)$",
      "target": "$1",
      "service": "html5-apps-repo-rt",
      "authenticationType": "xsuaa"
    }
  ]
}
```

## ui5.yaml

```yaml
specVersion: "3.1"
metadata:
  name: com.company.myapp
type: application
framework:
  name: SAPUI5
  version: "1.120.0"
  libraries:
    - name: sap.m
    - name: sap.ui.core
    - name: sap.ushell
    - name: sap.fe.templates
```

## Themes

| Theme              | Description                  |
| ------------------ | ---------------------------- |
| `sap_horizon`      | Default modern theme (2023+) |
| `sap_horizon_dark` | Dark mode variant            |
| `sap_horizon_hcb`  | High contrast black          |
| `sap_horizon_hcw`  | High contrast white          |
| `sap_fiori_3`      | Previous generation theme    |
