const form_regex = /form-\d-/i
function get_name_from_input(input) {
  return input.name.replace(form_regex, "");
}

function disable_submit_if_invalid() {
  if ($.find('.invalid-feedback').length > 0) {
    $('#save_all_answers').prop("disabled", true);
  } else {
    $('#save_all_answers').prop("disabled", false);
  }
}

$(function(){
  $('.form-select, .form-control, .form-check-input').on('blur', function(e){
    var $d = $(this);
    var $fs = $d.parents('fieldset');

    var csrf = $('input[name="csrfmiddlewaretoken"]').val()
    let data = {"csrfmiddlewaretoken": csrf};
    let has_values = false;
    $fs.find('.form-select, .form-control, input[type="hidden"]').each(function($i, $field) {
      let name = get_name_from_input($field);
      let $f = $( $field );
      let val = $( $field ).val();
      if (name != "question" && name != "authority" && val) {
        has_values = true;
      }
      data[name] = val;
    });
    if ( $fs.find('.form-check-input') ) {
      let $f = $fs.find('.form-check-input').get(0);
      let name = get_name_from_input($f);
      data[name] = $( $f.name ).val();
    }

    if (!has_values) {
      $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function($i, $field) {
        let $f = $($field);
        $f.removeClass("is-invalid").removeClass("is-valid");
        $f.next('.invalid-feedback').remove();
      });
      disable_submit_if_invalid()
      return;
    }

    url = window.location + data["question"] + "/";

    $.post(url, data, function(r_data) {
      if (r_data["success"] != 1) {
        $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function($i, $field) {
          let name = get_name_from_input($field);
          let $f = $($field);
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
        $fs.find('.form-select, .form-control, .form-check-input, input[type="hidden"]').each(function($i, $field) {
          let name = get_name_from_input($field);
          $f = $($field);
          $f.next('.invalid-feedback').remove();
          $f.addClass("is-valid").removeClass("is-invalid");
        });

        disable_submit_if_invalid()
      }
    });
  });
});
