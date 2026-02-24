# SAP Security & MTA Deployment Reference

## xs-security.json Structure

```json
{
  "xsappname": "my-app",
  "tenant-mode": "dedicated",
  "description": "Security descriptor for My App",
  "scopes": [
    { "name": "$XSAPPNAME.Read", "description": "Read access" },
    { "name": "$XSAPPNAME.Write", "description": "Write access" },
    { "name": "$XSAPPNAME.Admin", "description": "Admin access" }
  ],
  "attributes": [
    { "name": "Department", "description": "Department", "valueType": "string" }
  ],
  "role-templates": [
    {
      "name": "Viewer",
      "description": "Read-only access",
      "scope-references": ["$XSAPPNAME.Read"]
    },
    {
      "name": "Editor",
      "description": "Read and write access",
      "scope-references": ["$XSAPPNAME.Read", "$XSAPPNAME.Write"]
    },
    {
      "name": "Admin",
      "description": "Full access",
      "scope-references": [
        "$XSAPPNAME.Read",
        "$XSAPPNAME.Write",
        "$XSAPPNAME.Admin"
      ]
    }
  ],
  "role-collections": [
    {
      "name": "MyApp_Viewer",
      "role-template-references": ["$XSAPPNAME.Viewer"]
    },
    {
      "name": "MyApp_Admin",
      "role-template-references": ["$XSAPPNAME.Admin"]
    }
  ]
}
```

## CDS Authorization

```cds
// Service-level auth
@requires: 'authenticated-user'
service MyService {

  // Entity-level restrictions
  @restrict: [
    { grant: 'READ', to: 'Viewer' },
    { grant: ['CREATE', 'UPDATE'], to: 'Editor' },
    { grant: '*', to: 'Admin' }
  ]
  entity Orders as projection on db.Orders;

  // Instance-based auth (row-level)
  @restrict: [
    { grant: 'READ', where: 'createdBy = $user' },
    { grant: '*', to: 'Admin' }
  ]
  entity MyItems as projection on db.Items;
}
```

## .cdsrc.json

```json
{
  "[production]": {
    "auth": {
      "kind": "xsuaa"
    }
  },
  "[development]": {
    "auth": {
      "kind": "mocked",
      "users": {
        "admin": {
          "password": "admin",
          "roles": ["Admin", "Editor", "Viewer"]
        },
        "editor": { "password": "editor", "roles": ["Editor", "Viewer"] },
        "viewer": { "password": "viewer", "roles": ["Viewer"] }
      }
    }
  }
}
```

## mta.yaml Structure

```yaml
_schema-version: "3.1"
ID: my-app
version: 1.0.0
description: My SAP CAP Application

parameters:
  enable-parallel-deployments: true

build-parameters:
  before-all:
    - builder: custom
      commands:
        - npm ci
        - npx cds build --production

modules:
  # Backend Service
  - name: my-app-srv
    type: nodejs
    path: gen/srv
    parameters:
      buildpack: nodejs_buildpack
      memory: 256M
    requires:
      - name: my-app-auth
      - name: my-app-db
    provides:
      - name: srv-api
        properties:
          srv-url: ${default-url}

  # Database Deployer
  - name: my-app-db-deployer
    type: hdb
    path: gen/db
    parameters:
      buildpack: nodejs_buildpack
    requires:
      - name: my-app-db

  # UI Content
  - name: my-app-app-content
    type: com.sap.application.content
    path: .
    requires:
      - name: my-app-repo-host
        parameters:
          content-target: true
    build-parameters:
      build-result: resources
      requires:
        - name: my-app-ui
          artifacts:
            - ./*.zip
          target-path: resources/

  # Fiori App
  - name: my-app-ui
    type: html5
    path: app/orders
    build-parameters:
      build-result: dist
      builder: custom
      commands:
        - npm ci
        - npm run build
      supported-platforms: []

resources:
  # XSUAA Service
  - name: my-app-auth
    type: org.cloudfoundry.managed-service
    parameters:
      service: xsuaa
      service-plan: application
      path: ./xs-security.json

  # HDI Container
  - name: my-app-db
    type: com.sap.xs.hdi-container
    parameters:
      service: hana
      service-plan: hdi-shared

  # HTML5 Repository
  - name: my-app-repo-host
    type: org.cloudfoundry.managed-service
    parameters:
      service: html5-apps-repo
      service-plan: app-host
```

## package.json

```json
{
  "name": "my-app",
  "version": "1.0.0",
  "description": "SAP CAP Application",
  "repository": "",
  "license": "UNLICENSED",
  "private": true,
  "dependencies": {
    "@sap/cds": "^8",
    "express": "^4",
    "@sap/xssec": "^4",
    "passport": "^0"
  },
  "devDependencies": {
    "@sap/cds-dk": "^8",
    "@sap/ux-specification": "latest",
    "rimraf": "^5"
  },
  "scripts": {
    "start": "cds-serve",
    "build": "cds build --production",
    "watch": "cds watch",
    "test": "jest"
  },
  "cds": {
    "requires": {
      "db": {
        "kind": "sql"
      },
      "[production]": {
        "db": { "kind": "hana" },
        "auth": { "kind": "xsuaa" }
      }
    },
    "hana": { "deploy-format": "hdbtable" }
  }
}
```
