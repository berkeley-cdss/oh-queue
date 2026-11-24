import { Link, Navigate } from "react-router-dom";
import React from "react";
import { app } from "../app_instance";
import { Messages } from "./messages";
import { Navbar } from "./navbar";
import { OfflineIndicator } from "./offline_indicator";
import { Pager } from "./pager";
import { Row } from "./row";
import { Tab, Tabs } from "./tabs";

export function ActivityLogLayout({ state }) {
  const [activeTab, setActiveTab] = React.useState(0);

  const [userList, setUserList] = React.useState([]);
  const [isLoading, setIsLoading] = React.useState(false);

  const [searchText, setSearchText] = React.useState("");

  if (state.currentUser && !state.currentUser.isStaff) {
    return <Navigate to={`/user/${state.currentUser.id}`} replace />;
  }

  if (app && !isLoading && userList.length === 0) {
    setIsLoading(true);
    app.makeRequest("list_users", (users) => {
      setUserList(users);
    });
  }

  const foundUsers = userList.filter(({ name, email }) =>
    (name + email).toLowerCase().includes(searchText.toLowerCase()),
  );

  return (
    <div>
      <Navbar state={state} mode="activity_log" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <main>
        <div className="hero">
          <div className="container">
            <h2>Activity Log</h2>
            <p>View the activity of any user of the queue.</p>
            <div className="mb-3">
              <form>
                <div className="input-group activity-search">
                  <input
                    className="form-control"
                    type="search"
                    aria-label="Search for a student or a member of staff"
                    placeholder="Search for a student or a member of staff"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                  />
                  <button className="btn btn-outline-secondary" type="button">
                    Search
                  </button>
                </div>
              </form>
            </div>
            <div className="activity-buttons">
              <Link
                to={`/user/${state.currentUser && state.currentUser.id}`}
                className="btn btn-primary"
              >
                My activity
              </Link>
              <Link to="/activity_log" className="btn btn-warning">
                Class Overview
              </Link>
            </div>
          </div>
        </div>

        <div className="container">
          <Messages messages={state.messages} />

          {searchText ? (
            <Tabs selectedIndex={0} onSelect={() => null}>
              <Tab label={`Search Results (${foundUsers.length})`}>
                {/* keyed, so each search starts on its first page */}
                <UserList key={searchText} users={foundUsers} />
              </Tab>
            </Tabs>
          ) : (
            <Tabs selectedIndex={activeTab} onSelect={setActiveTab}>
              <Tab label="Staff">
                <UserList
                  key="staff"
                  users={userList.filter(({ isStaff }) => isStaff)}
                />
              </Tab>
              <Tab label="Students">
                <UserList
                  key="students"
                  users={userList.filter(({ isStaff }) => !isStaff)}
                />
              </Tab>
            </Tabs>
          )}
        </div>
      </main>
    </div>
  );
}

export function UserList({ users }) {
  const [page, setPage] = React.useState(0);

  return (
    <div>
      <div className="queue">
        {users.slice(page * 50, (page + 1) * 50).map((user) => (
          <User key={user.id} user={user} />
        ))}
      </div>
      <Pager page={page} setPage={setPage} pages={users.length / 50} />
    </div>
  );
}

export function User({ user }) {
  return (
    <Row
      title={user.name}
      link={`/user/${user.id}`}
      prop1={user.email}
      prop2={`Role: ${user.isStaff ? "Staff" : "Student"}`}
    />
  );
}
