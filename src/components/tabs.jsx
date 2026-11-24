import classNames from "classnames";
import React from "react";

/* Tabs, with the keyboard behavior and roles of WAI-ARIA's tabs pattern
 * (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/). Use like this:
 *
 * <Tabs selectedIndex={0} onSelect={(index) => ...}>
 *   <Tab label="My Tab">
 *     ... tab content
 *   </Tab>
 *   <Tab label="Other Tab">
 *     ... tab content
 *   </Tab>
 * </Tabs>
 */
export let Tabs = ({ selectedIndex, onSelect, children }) => {
  const id = React.useId();
  const tabRefs = React.useRef([]);
  const tabs = React.Children.toArray(children).filter((x) => x);

  // The arrow keys, Home and End move between the tabs, choosing the one they move to.
  const onKeyDown = (e, index) => {
    const last = tabs.length - 1;
    const next = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      Home: 0,
      End: last,
    }[e.key];
    if (next !== undefined) {
      e.preventDefault();
      onSelect(next);
      tabRefs.current[next]?.focus();
    }
  };

  return (
    <div className="tabs-container">
      <ul className="nav nav-tabs nav-justified" role="tablist">
        {tabs.map((child, index) => {
          const active = selectedIndex === index;
          return (
            <li key={index} className="nav-item" role="presentation">
              <button
                type="button"
                role="tab"
                id={`${id}-tab-${index}`}
                ref={(element) => {
                  tabRefs.current[index] = element;
                }}
                aria-selected={active}
                aria-controls={`${id}-panel`}
                tabIndex={active ? 0 : -1}
                className={classNames("nav-link", {
                  active,
                  pulsating: child.props.shouldHighlight && !active,
                })}
                onClick={() => onSelect(index)}
                onKeyDown={(e) => onKeyDown(e, index)}
              >
                {child.props.label}
              </button>
            </li>
          );
        })}
      </ul>
      <div
        className="tab-content"
        role="tabpanel"
        id={`${id}-panel`}
        aria-labelledby={`${id}-tab-${selectedIndex}`}
      >
        {tabs[selectedIndex]}
      </div>
    </div>
  );
};

export const Tab = (props) => {
  return <div>{props.children}</div>;
};
