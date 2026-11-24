import React from "react";

export class SelectPicker extends React.Component {
  constructor(...args) {
    super(...args);

    this.selectRef = React.createRef();
    this.refreshSelect = this.refreshSelect.bind(this);
  }
  componentDidMount() {
    this.refreshSelect();
  }
  refreshSelect() {
    const select = this.selectRef.current;
    $(select).selectpicker("refresh");
    // bootstrap-select chooses its title placeholder when it first sets up a
    // select whose option React chose, so a controlled select's value is
    // chosen again.
    const { value } = this.props;
    if (value != null) {
      $(select).selectpicker("val", String(value));
    }
  }
  componentDidUpdate() {
    this.refreshSelect();
  }
  render() {
    var { options, emptyOption } = this.props;
    if (options && !Array.isArray(options) && typeof options === "object") {
      options = Object.entries(options).map((entry) =>
        Object.assign(
          {},
          {
            id: entry[0],
          },
          entry[1],
        ),
      );
    }
    var optionsElements = null;
    if (options) {
      optionsElements = options
        .map((obj) => {
          if (typeof obj === "string") {
            return (
              <option key={obj} value={obj}>
                {obj}
              </option>
            );
          } else if (obj.id !== undefined && obj.name !== undefined) {
            return (
              <option key={obj.id} value={obj.id}>
                {obj.name}
              </option>
            );
          } else {
            let str = JSON.stringify(obj);
            return (
              <option key={str} value={str}>
                {str}
              </option>
            );
          }
        })
        .filter((option) => option);
    }
    var props = Object.assign({}, this.props);
    delete props.emptyOption;
    delete props.options;
    return (
      <select ref={this.selectRef} {...props}>
        {emptyOption && <option value="">{emptyOption}</option>}
        {optionsElements}
      </select>
    );
  }
}
