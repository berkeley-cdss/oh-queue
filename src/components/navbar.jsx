import Container from "react-bootstrap/Container";
import Nav from "react-bootstrap/Nav";
import BootstrapNavbar from "react-bootstrap/Navbar";
import NavDropdown from "react-bootstrap/NavDropdown";
import React from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { isPartyRoot, loginPath } from "../common";
import { getMyGroup, getMyTicket } from "../state";

// The site header, as on the pages outside a course (oh_queue/templates/pages/base.html)
// and in sections and seating: the course as its heading, with the page's name for
// screen readers; the course's pages on the left; and the way out (Offerings, and the
// account menu with Log Out) on the right.
export let Navbar = ({ state, mode }) => {
  var { currentUser } = state;
  var myTicket = getMyTicket(state);
  if (myTicket && myTicket.group_id) {
    myTicket = null;
  }
  const myGroup = getMyGroup(state);

  // On narrow screens, close the menu once a link in it goes to another page.
  const [expanded, setExpanded] = React.useState(false);
  const location = useLocation();
  const [prevLocation, setPrevLocation] = React.useState(location);
  if (location !== prevLocation) {
    setPrevLocation(location);
    setExpanded(false);
  }

  const words = mode.split("_");

  if (words.length === 1 && words[0] === "party") {
    words[0] = state.config.party_name;
  }

  const title = words
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");

  const partyAsRoot = isPartyRoot(state);
  const isStaff = !!currentUser && currentUser.isStaff;

  return (
    <BootstrapNavbar
      expand="lg"
      bg="primary"
      data-bs-theme="dark"
      className="site-header"
      expanded={expanded}
      onToggle={setExpanded}
    >
      <Container fluid>
        {/* the page this is; its top-level heading */}
        <h1 className="site-title">
          <BootstrapNavbar.Brand as={Link} to="/">
            {window.courseName}
            <span className="visually-hidden"> | {title}</span>
          </BootstrapNavbar.Brand>
        </h1>
        <BootstrapNavbar.Toggle aria-controls="site-nav" />
        <BootstrapNavbar.Collapse id="site-nav">
          <Nav className="me-auto">
            {!!myGroup && (
              <Nav.Link as={NavLink} to={`/groups/${myGroup.id}/`}>
                My Group
              </Nav.Link>
            )}
            {!!myTicket && (
              <Nav.Link as={NavLink} to={`/tickets/${myTicket.id}/`}>
                My Request
              </Nav.Link>
            )}
            {currentUser && state.config.party_enabled && (
              <Nav.Link as={NavLink} to={partyAsRoot ? "/" : "/party"} end>
                {state.config.party_name}
              </Nav.Link>
            )}
            {currentUser && (
              <Nav.Link as={NavLink} to={partyAsRoot ? "/queue" : "/"} end>
                Queue
              </Nav.Link>
            )}
            {currentUser && (
              <Nav.Link as={NavLink} to={`/user/${currentUser.id}`} end>
                Ticket History
              </Nav.Link>
            )}
            {isStaff && (
              <Nav.Link as={NavLink} to="/activity_log">
                Activity Log
              </Nav.Link>
            )}
            {isStaff && (
              <Nav.Link as={NavLink} to="/admin">
                Admin
              </Nav.Link>
            )}
            {isStaff && state.config.online_active && (
              <Nav.Link as={NavLink} to="/online_setup">
                Online Setup
              </Nav.Link>
            )}
          </Nav>
          <Nav>
            {currentUser ? (
              <>
                <Nav.Link href="/offerings">Offerings</Nav.Link>
                <NavDropdown
                  title={currentUser.name}
                  id="account-menu"
                  align="end"
                  data-bs-theme="light"
                >
                  {/* A POST, so other sites can't sign people out. */}
                  <form method="post" action="/logout/">
                    <button type="submit" className="dropdown-item">
                      Log Out
                    </button>
                  </form>
                </NavDropdown>
              </>
            ) : (
              <Nav.Link href={loginPath()}>Login</Nav.Link>
            )}
          </Nav>
        </BootstrapNavbar.Collapse>
      </Container>
    </BootstrapNavbar>
  );
};
