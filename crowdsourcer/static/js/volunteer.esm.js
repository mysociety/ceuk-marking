async function getAvailableAuthorities($fs) {
    var url = "/volunteers/available_authorities/";

    var $section = $fs.find('.field_section').eq(0);
    var $rt = $fs.find('.field_rt').eq(0);
    var $id = $fs.find('[name$="-id"]').eq(0);

    if ($rt.val() == "" || $section.val() == "") {
      return { results: [] };
    }

    var params = {
      rt: $rt.val(),
      s: $section.val(),
      ms: $fs.find('.field_session').eq(0).val()
    };


    if ($id.val()) {
      params['id'] = $id.val();
    }

    url = url + '?' + $.param(params);

    const response = await fetch(url, {
        method: 'GET',
        mode: 'cors',
        credentials: 'same-origin',
        headers: {
            "Content-Type": 'application/x-www-form-urlencoded',
            "Accept": 'application/json; charset=utf-8',
        },
    })

    return response.json()
}
$(function(){
  $('.field_rt,.field_section').on('change', function(e){
    var $d = $(this);
    var $fs = $d.parents('fieldset');

    var $a = $fs.find('.field_authority').eq(0);

    getAvailableAuthorities($fs).then(function(data){
      if (data["results"].length > 0) {
        $a.empty()
        let $blank = $('<option></option>').text("---------");
        $a.append($blank);
        $.each(data["results"], function(i, opt) {
          let $o = $('<option></option>').attr('value', opt["id"]).text(opt["name"]);
          $a.append($o)
        });
      }
    });
  });
});
