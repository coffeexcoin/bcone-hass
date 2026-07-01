class BconePoolCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("bcone-pool-card-editor");
  }

  static getStubConfig() {
    return {
      type: "custom:bcone-pool-card",
      state_entity: "",
      sensitivity_entity: "",
      stop_siren_entity: "",
    };
  }

  setConfig(config) {
    if (!config.state_entity && !config.entity) {
      throw new Error("BCone Pool Card requires state_entity");
    }
    this._config = { ...config, state_entity: config.state_entity || config.entity };
    this._root = this._root || this.attachShadow({ mode: "open" });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    if (!this._root || !this._config || !this._hass) {
      return;
    }

    const entities = this._entities();
    const stateObj = this._state(entities.state);
    const sensitivityObj = this._state(entities.sensitivity);
    const temperatureObj = this._state(entities.temperature);
    const batteryObj = this._state(entities.battery);
    const rssiObj = this._state(entities.rssi);
    const positionObj = this._state(entities.position);
    const alarmObj = this._state(entities.alarm);
    const mqttObj = this._state(entities.mqtt);
    const canControlState = stateObj && !["unavailable", "unknown"].includes(stateObj.state);
    const canControlSensitivity = sensitivityObj && !["unavailable", "unknown"].includes(sensitivityObj.state);
    const title = this._config.name || this._friendlyName(stateObj, "BCone Pool");
    const sensitivity = Number.parseFloat(sensitivityObj?.state);

    this._root.innerHTML = `
      <ha-card>
        <style>
          :host {
            display: block;
          }
          .card {
            padding: 16px;
          }
          .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 14px;
          }
          .title {
            min-width: 0;
            font-size: 18px;
            font-weight: 500;
            line-height: 1.25;
          }
          .badge {
            flex: none;
            border-radius: 999px;
            padding: 4px 9px;
            font-size: 12px;
            line-height: 1.2;
            color: var(--primary-background-color);
            background: var(--state-icon-color);
          }
          .badge.on {
            background: var(--success-color, #43a047);
          }
          .badge.problem {
            background: var(--error-color, #db4437);
          }
          .modes {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 16px;
          }
          button {
            min-width: 0;
            border: 1px solid var(--divider-color);
            border-radius: 8px;
            padding: 9px 8px;
            color: var(--primary-text-color);
            background: var(--card-background-color);
            font: inherit;
            cursor: pointer;
          }
          button[disabled] {
            cursor: not-allowed;
            opacity: 0.45;
          }
          button.active {
            border-color: var(--primary-color);
            color: var(--text-primary-color);
            background: var(--primary-color);
          }
          .slider-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 12px;
            align-items: center;
            margin-bottom: 16px;
          }
          .label {
            color: var(--secondary-text-color);
            font-size: 13px;
            margin-bottom: 6px;
          }
          .value {
            font-size: 15px;
            font-weight: 500;
          }
          input[type="range"] {
            width: 100%;
            margin: 0;
            accent-color: var(--primary-color);
          }
          .metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 14px;
          }
          .metric {
            min-width: 0;
            border-top: 1px solid var(--divider-color);
            padding-top: 9px;
          }
          .metric .value {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .actions {
            display: flex;
            justify-content: flex-end;
          }
          .stop {
            border-color: var(--error-color, #db4437);
            color: var(--error-color, #db4437);
          }
          .empty {
            color: var(--secondary-text-color);
            font-size: 13px;
          }
        </style>
        <div class="card">
          <div class="header">
            <div class="title">${this._escape(title)}</div>
            ${this._statusBadge(stateObj, alarmObj, mqttObj)}
          </div>
          <div class="modes">
            ${this._modeButton("On/Armed", stateObj?.state, canControlState)}
            ${this._modeButton("Off/Disarmed", stateObj?.state, canControlState)}
            ${this._modeButton("Swim Mode", stateObj?.state, canControlState)}
          </div>
          ${sensitivityObj ? this._sensitivityControl(sensitivity, canControlSensitivity) : ""}
          <div class="metrics">
            ${this._metric("Temperature", temperatureObj)}
            ${this._metric("Battery", batteryObj)}
            ${this._metric("Position", positionObj)}
            ${this._metric("RSSI", rssiObj)}
          </div>
          ${this._actions(entities.stopSiren)}
          ${!stateObj ? `<div class="empty">State entity not found.</div>` : ""}
        </div>
      </ha-card>
    `;

    this._root.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => this._selectMode(button.dataset.mode));
    });
    this._root.querySelector("[data-sensitivity]")?.addEventListener("change", (event) => {
      this._setSensitivity(Number.parseFloat(event.target.value));
    });
    this._root.querySelector("[data-stop-siren]")?.addEventListener("click", () => this._stopSiren());
  }

  _entities() {
    return {
      state: this._config.state_entity,
      sensitivity: this._config.sensitivity_entity || this._findCompanion("number", ["sensitivity"]),
      stopSiren: this._config.stop_siren_entity || this._findCompanion("button", ["stop siren"]),
      temperature: this._config.temperature_entity || this._findCompanion("sensor", ["temperature"]),
      battery: this._config.battery_entity || this._findCompanion("sensor", ["battery voltage", "battery"]),
      rssi: this._config.rssi_entity || this._findCompanion("sensor", ["rssi"]),
      position: this._config.position_entity || this._findCompanion("sensor", ["position"]),
      alarm: this._config.alarm_entity || this._findCompanion("binary_sensor", ["alarm active"]),
      mqtt: this._config.mqtt_entity || this._findCompanion("binary_sensor", ["mqtt connected"]),
    };
  }

  _findCompanion(domain, needles) {
    const entities = this._hass?.entities;
    const stateEntity = this._config?.state_entity;
    const source = entities?.[stateEntity];
    if (!entities || (!source?.device_id && !source?.config_entry_id)) {
      return undefined;
    }

    const matches = [];
    for (const [entityId, registryEntity] of Object.entries(entities)) {
      const sameDevice = source.device_id && registryEntity.device_id === source.device_id;
      const sameEntry = source.config_entry_id && registryEntity.config_entry_id === source.config_entry_id;
      if (!entityId.startsWith(`${domain}.`) || (!sameDevice && !sameEntry)) {
        continue;
      }
      const stateObj = this._hass.states[entityId];
      const haystack = [
        registryEntity.name,
        registryEntity.original_name,
        stateObj?.attributes?.friendly_name,
        entityId.replace(`${domain}.`, "").replaceAll("_", " "),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (needles.some((needle) => haystack.includes(needle))) {
        matches.push({ entityId, rank: sameDevice ? 0 : 1 });
      }
    }
    return matches.sort((left, right) => left.rank - right.rank || left.entityId.localeCompare(right.entityId))[0]?.entityId;
  }

  _state(entityId) {
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _friendlyName(stateObj, fallback) {
    return stateObj?.attributes?.friendly_name || fallback;
  }

  _statusBadge(stateObj, alarmObj, mqttObj) {
    if (alarmObj?.state === "on") {
      return `<div class="badge problem">Alarm</div>`;
    }
    if (stateObj?.state && !["unavailable", "unknown"].includes(stateObj.state)) {
      return `<div class="badge on">${this._escape(stateObj.state)}</div>`;
    }
    if (mqttObj?.state === "off") {
      return `<div class="badge">MQTT off</div>`;
    }
    return `<div class="badge">Unavailable</div>`;
  }

  _modeButton(mode, current, enabled) {
    const active = current === mode ? " active" : "";
    const disabled = enabled ? "" : " disabled";
    return `<button class="${active}" data-mode="${this._escape(mode)}"${disabled}>${this._escape(mode)}</button>`;
  }

  _sensitivityControl(value, enabled) {
    const safeValue = Number.isFinite(value) ? value : 1;
    return `
      <div class="slider-row">
        <div>
          <div class="label">Sensitivity</div>
          <input data-sensitivity type="range" min="1" max="5" step="0.5" value="${safeValue}"${enabled ? "" : " disabled"}>
        </div>
        <div class="value">${Number.isFinite(value) ? value.toFixed(1) : "Unknown"}</div>
      </div>
    `;
  }

  _metric(label, stateObj) {
    if (!stateObj) {
      return "";
    }
    const unit = stateObj.attributes?.unit_of_measurement || "";
    const value = ["unknown", "unavailable"].includes(stateObj.state)
      ? "Unknown"
      : `${stateObj.state}${unit ? ` ${unit}` : ""}`;
    return `
      <div class="metric">
        <div class="label">${this._escape(label)}</div>
        <div class="value">${this._escape(value)}</div>
      </div>
    `;
  }

  _actions(stopSirenEntity) {
    if (this._config.show_stop_siren === false || !stopSirenEntity) {
      return "";
    }
    const disabled = this._state(stopSirenEntity)?.state === "unavailable" ? " disabled" : "";
    return `
      <div class="actions">
        <button class="stop" data-stop-siren${disabled}>Stop Siren</button>
      </div>
    `;
  }

  _selectMode(option) {
    if (!this._config.state_entity) {
      return;
    }
    this._hass.callService("select", "select_option", {
      entity_id: this._config.state_entity,
      option,
    });
  }

  _setSensitivity(value) {
    const entityId = this._entities().sensitivity;
    if (!entityId || !Number.isFinite(value)) {
      return;
    }
    this._hass.callService("number", "set_value", {
      entity_id: entityId,
      value,
    });
  }

  _stopSiren() {
    const entityId = this._entities().stopSiren;
    if (!entityId) {
      return;
    }
    this._hass.callService("button", "press", {
      entity_id: entityId,
    });
  }

  _escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

class BconePoolCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) {
      return;
    }
    this.innerHTML = `
      <style>
        .field {
          display: block;
          margin-bottom: 12px;
        }
      </style>
      ${this._selector("name", "Name", "Optional card title")}
      ${this._selector("state_entity", "State entity", "select.pool_state")}
      ${this._selector("sensitivity_entity", "Sensitivity entity", "number.pool_sensitivity")}
      ${this._selector("stop_siren_entity", "Stop siren entity", "button.bcone_stop_siren")}
      ${this._selector("temperature_entity", "Temperature entity", "sensor.pool_temperature")}
      ${this._selector("battery_entity", "Battery entity", "sensor.pool_battery_voltage")}
      ${this._selector("rssi_entity", "RSSI entity", "sensor.pool_rssi")}
      ${this._selector("position_entity", "Position entity", "sensor.pool_position")}
    `;
    this.querySelectorAll("ha-textfield").forEach((field) => {
      field.addEventListener("input", (event) => {
        this._valueChanged(event.target.dataset.key, event.target.value);
      });
    });
  }

  _selector(key, label, placeholder) {
    return `
      <ha-textfield
        class="field"
        data-key="${key}"
        label="${label}"
        placeholder="${placeholder}"
        value="${this._escape(this._config?.[key] || "")}"
      ></ha-textfield>
    `;
  }

  _valueChanged(key, value) {
    const config = { ...this._config };
    if (value) {
      config[key] = value;
    } else {
      delete config[key];
    }
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  _escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

customElements.define("bcone-pool-card", BconePoolCard);
customElements.define("bcone-pool-card-editor", BconePoolCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bcone-pool-card",
  name: "BCone Pool Card",
  description: "Controls and status for a BCone pool unit.",
});
