import classNames from "classnames";

// A native select of options: strings, or objects with an id and a name. A native
// select works with the keyboard and screen readers as people expect, and on phones
// opens the phone's own picker. It's named by its title, unless it has a label.
//
// placeholder: shown, and chosen, until something else is (with `required`, the form
// can't be sent until then). emptyOption: a choice that means none, such as "Any".
export function SelectPicker({
  options,
  emptyOption,
  placeholder,
  size,
  className,
  ...props
}) {
  if (options && !Array.isArray(options) && typeof options === "object") {
    options = Object.entries(options).map(([id, option]) => ({
      id,
      ...option,
    }));
  }
  const optionElements = (options || []).map((option) => {
    if (typeof option === "string") {
      return (
        <option key={option} value={option}>
          {option}
        </option>
      );
    } else if (option.id !== undefined && option.name !== undefined) {
      return (
        <option key={option.id} value={option.id}>
          {option.name}
        </option>
      );
    } else {
      const text = JSON.stringify(option);
      return (
        <option key={text} value={text}>
          {text}
        </option>
      );
    }
  });
  // Uncontrolled, a placeholder is chosen to start with.
  const defaultValue =
    placeholder && props.value === undefined && props.defaultValue === undefined
      ? ""
      : props.defaultValue;
  return (
    <select
      className={classNames(
        "form-select",
        size && `form-select-${size}`,
        className,
      )}
      aria-label={props["aria-labelledby"] ? undefined : props.title}
      {...props}
      defaultValue={defaultValue}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {emptyOption && <option value="">{emptyOption}</option>}
      {optionElements}
    </select>
  );
}
