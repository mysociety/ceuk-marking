const form_regex = /form-\d+-/i
function get_name_from_input(input) {
  return input.name.replace(form_regex, "");
}

function disable_submit_if_invalid() {
  if ($('.invalid-feedback').length > 0) {
    $('#save_all_answers').prop("disabled", true);
  } else {
    $('#save_all_answers').prop("disabled", false);
  }
}

$(function(){
  $('.form-select, .form-control, .form-check-input').on('blur', function(e){
    // if we have submitted the form then do not check as it might create duplicates
    if (e.relatedTarget && e.relatedTarget.id == "save_all_answers" && $(e.relatedTarget).prop("disabled") == false) {
      return;
    }
    var $d = $(this);
    var $fs = $d.parents('fieldset');

    var csrf = $d.parents('form').find('input[name="csrfmiddlewaretoken"]').val()
    let data = {"csrfmiddlewaretoken": csrf};
    let has_values = false;
    $fs.find('.form-select, .form-control, input[type="hidden"]').each(function() {
      let $f = $(this);
      let name = get_name_from_input($f[0]);
      let val = $f.val();
      if (name != "question" && name != "authority" && val) {
        has_values = true;
      }
      data[name] = val;
    });
    if ( $fs.find('.form-check-input').length ) {
      let f = $fs.find('.form-check-input').get(0);
      let name = get_name_from_input(f);
      let val = []
      data[name] = $fs.find('.form-check-input:checked').map(function(_, e) {
        return $(e).val();
      }).get();
    }

    if (!has_values) {
      $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function() {
        let $f = $(this);
        $f.removeClass("is-invalid is-valid");
        $f.next('.invalid-feedback').remove();
      });
      disable_submit_if_invalid()
      return;
    }

    let url_parts = [window.location.protocol, '//', window.location.host, window.location.pathname, data["question"], "/"];
    let url = url_parts.join("");

    $.post({ url: url, data: data, traditional: true, success: function(r_data) {
      if (r_data["success"] != 1) {
        $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function() {
          let $f = $(this);
          let name = get_name_from_input($f[0]);
          $f.next('.invalid-feedback').remove();
          if (r_data["errors"].hasOwnProperty(name)) {
            $f.addClass("is-invalid").removeClass("is-valid");
            $f.after('<div class="invalid-feedback">' + r_data["errors"][name] + '</div>');
          } else {
            $f.addClass("is-valid").removeClass("is-invalid");
          }
        });
        $('#save_all_answers').prop("disabled", true);
      } else {
        $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function() {
          $f = $(this);
          let name = get_name_from_input($f[0]);
          $f.next('.invalid-feedback').remove();
          $f.addClass("is-valid").removeClass("is-invalid");
        });

        disable_submit_if_invalid()
      }
    }});
  });
});
