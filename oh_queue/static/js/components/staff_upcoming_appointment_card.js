function StaffUpcomingAppointmentCard({ appointment, locations, assignments }) {
  const possessive = appointment.helper ? "Your" : "This";

  const descriptionText = appointment.description && (
    <React.Fragment>
      It will be on the subject of <b>{appointment.description}</b>.
    </React.Fragment>
  );

  const makeAppointmentsString = () => 
    {
      const arr = appointment.signups.map((signup) => {
          const assignmentText = signup.assignment_id
            ? assignments[signup.assignment_id].name
            : "";
          const questionText =
            (signup.assignment_id ? " " : "") +
            (parseInt(signup.question) ? "Q" : "") +
            (signup.question || "");
          return signup.user.name + " (" + assignmentText + questionText + ")";
        })
      if (arr.length === 0) {
        return "";
      }
      const listStart = arr.slice(0, -1).join(', ')
      const listEnd = arr.slice(-1)
      const conjunction = arr.length <= 1
        ? ''
        : arr.length > 2
          ? ', and '
          : ' and '
      const joined = arr.length >= 2 ? "have joined your appointment." : "has joined your appointment.";
      return [listStart, listEnd].join(conjunction) + " " + joined;
    }

  const appointmentStudents = appointment.helper ? makeAppointmentsString() : "";

  const content = (
    <React.Fragment>
      {possessive} appointment is at{" "}
      <b>{locations[appointment.location_id].name}</b>, with a group of{" "}
      <b>{appointment.signups.length}</b> students. {descriptionText}
      {appointmentStudents}
    </React.Fragment>
  );

  const history = ReactRouterDOM.useHistory();

  const handleClick = (e) => {
    e.preventDefault();
    history.push("/appointments/" + appointment.id);
  };

  const style = {};

  if (!appointment.helper) {
    style.borderLeft = "5px solid red";
  }

  if (appointment.status === "active") {
    style.borderLeft = "5px solid #337ab7";
  }
  
  const hasStudent = !!appointment.signups.length && appointment.helper;
  
  if (hasStudent) {
    style.borderLeft = "5px solid #009688";
  }

  return (
    <div className="panel panel-default" onClick={handleClick} style={style}>
      <ul className="list-group">
        <a href="#" className="list-group-item">
          {!appointment.helper && (
            <span className="badge badge-danger">No helper assigned!</span>
          )}
          {appointment.status === "active" && (
            <span className="badge badge-primary">In Progress</span>
          )}
          <h4 className={"list-group-item-heading appointment-card-heading" + (hasStudent ? " appointment-card-heading-success" : "")}>
            {formatAppointmentDate(appointment)}
          </h4>
          <div className="appointment-card-subheading">
            {formatAppointmentDuration(appointment)}
          </div>
          {content}
        </a>
      </ul>
    </div>
  );
}
