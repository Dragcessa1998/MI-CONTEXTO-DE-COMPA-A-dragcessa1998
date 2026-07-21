/*
 * validation.js — Validación del formulario de registro de talento (Nexova · Hito 1)
 *
 * Valida en tiempo real (al perder el foco y mientras se corrige) y al enviar.
 * Los mensajes de error son específicos y coherentes con los campos del formulario.
 * No envía datos a ningún sitio: simula el envío mostrando un mensaje de éxito.
 */
(function () {
  'use strict';

  // ----- Mensajes de error específicos por campo -----
  const MSG = {
    fullName: 'El nombre debe contener al menos nombre y apellido',
    email: 'Ingresa un email válido (ejemplo: nombre@empresa.com)',
    phone: 'El teléfono debe incluir código de país (ejemplo: +34 612 345 678)',
    country: 'Selecciona tu país de residencia',
    experience: 'Los años de experiencia deben estar entre 0 y 50',
    sector: 'Selecciona el sector de tu interés',
    english: 'Indica tu nivel de inglés',
    availability: 'Selecciona tu disponibilidad',
    linkedin: 'Si incluyes LinkedIn, debe ser una URL válida',
    dataPolicy: 'Debes aceptar la política de tratamiento de datos para continuar'
  };

  const MAX_COMMENTS = 500;

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('talent-form');
    if (!form) return;

    const $ = function (id) { return document.getElementById(id); };
    const successBox = $('success-message');
    const counter = $('comments-counter');
    const availabilityGroup = $('availability-group');
    const availabilityOptions = form.querySelectorAll('[data-availability-option]');

    // Elementos de entrada por nombre de campo
    const inputs = {
      fullName: $('fullName'),
      email: $('email'),
      phone: $('phone'),
      country: $('country'),
      linkedin: $('linkedin'),
      experience: $('experience'),
      sector: $('sector'),
      english: $('english'),
      comments: $('comments'),
      dataPolicy: $('dataPolicy')
    };

    // ----- Validadores: devuelven '' si es válido, o el mensaje de error -----
    const validators = {
      fullName: function () {
        const words = inputs.fullName.value.trim().split(/\s+/).filter(Boolean);
        return words.length >= 2 ? '' : MSG.fullName;
      },
      email: function () {
        const v = inputs.email.value.trim();
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? '' : MSG.email;
      },
      phone: function () {
        // Debe comenzar con + y código de país; entre 8 y 16 dígitos en total
        const compact = inputs.phone.value.trim().replace(/\s+/g, '');
        return /^\+\d{8,16}$/.test(compact) ? '' : MSG.phone;
      },
      country: function () {
        return inputs.country.value ? '' : MSG.country;
      },
      experience: function () {
        const raw = inputs.experience.value.trim();
        if (raw === '') return MSG.experience;
        const n = Number(raw);
        return (Number.isFinite(n) && n >= 0 && n <= 50) ? '' : MSG.experience;
      },
      sector: function () {
        return inputs.sector.value ? '' : MSG.sector;
      },
      english: function () {
        return inputs.english.value ? '' : MSG.english;
      },
      availability: function () {
        return form.querySelector('input[name="availability"]:checked') ? '' : MSG.availability;
      },
      linkedin: function () {
        const v = inputs.linkedin.value.trim();
        if (v === '') return ''; // opcional
        return /^https?:\/\/[^\s]+\.[^\s]+$/i.test(v) ? '' : MSG.linkedin;
      },
      comments: function () {
        const len = inputs.comments.value.length;
        if (len > MAX_COMMENTS) {
          return 'Los comentarios no pueden exceder 500 caracteres (quedan ' + (MAX_COMMENTS - len) + ')';
        }
        return '';
      },
      dataPolicy: function () {
        return inputs.dataPolicy.checked ? '' : MSG.dataPolicy;
      }
    };

    // Orden de validación (también define a qué campo saltar el foco)
    const ORDER = ['fullName', 'email', 'phone', 'country', 'experience',
      'sector', 'english', 'availability', 'linkedin', 'comments', 'dataPolicy'];

    // ----- Pintar / limpiar el estado visual de un campo -----
    function setFieldState(name, message) {
      const errorEl = $('error-' + name);
      const input = inputs[name]; // puede ser undefined para 'availability'

      if (name === 'availability') {
        availabilityGroup.setAttribute('aria-invalid', message ? 'true' : 'false');
        availabilityOptions.forEach(function (option) {
          option.classList.toggle('border-red-500', Boolean(message));
          option.classList.toggle('border-slate-300', !message);
        });
      }

      if (message) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
        if (input) {
          input.setAttribute('aria-invalid', 'true');
          input.classList.add('border-red-500');
          input.classList.remove('border-slate-300');
        }
      } else {
        errorEl.textContent = '';
        errorEl.classList.add('hidden');
        if (input) {
          input.setAttribute('aria-invalid', 'false');
          input.classList.add('border-slate-300');
          input.classList.remove('border-red-500');
        }
      }
    }

    function validateField(name) {
      const message = validators[name]();
      setFieldState(name, message);
      return message === '';
    }

    // ----- Validación en tiempo real -----
    // Campos de texto: validar al salir del foco; corregir en vivo si ya hay error
    ['fullName', 'email', 'phone', 'linkedin', 'experience'].forEach(function (name) {
      inputs[name].addEventListener('blur', function () { validateField(name); });
      inputs[name].addEventListener('input', function () {
        if (!$('error-' + name).classList.contains('hidden')) validateField(name);
      });
    });

    // Selects: validar al cambiar
    ['country', 'sector', 'english'].forEach(function (name) {
      inputs[name].addEventListener('change', function () { validateField(name); });
    });

    // Radios de disponibilidad
    form.querySelectorAll('input[name="availability"]').forEach(function (radio) {
      radio.addEventListener('change', function () { validateField('availability'); });
    });

    // Checkbox de política
    inputs.dataPolicy.addEventListener('change', function () { validateField('dataPolicy'); });

    // Comentarios: contador en vivo + validación de longitud
    function updateCounter() {
      const remaining = MAX_COMMENTS - inputs.comments.value.length;
      counter.textContent = 'Quedan ' + remaining + ' caracteres';
      counter.classList.toggle('text-red-600', remaining < 0);
      counter.classList.toggle('text-slate-500', remaining >= 0);
      validateField('comments');
    }
    inputs.comments.addEventListener('input', updateCounter);

    // ----- Envío -----
    form.addEventListener('submit', function (e) {
      e.preventDefault(); // siempre: no hay backend todavía
      let firstInvalid = null;
      ORDER.forEach(function (name) {
        const ok = validateField(name);
        if (!ok && firstInvalid === null) firstInvalid = name;
      });

      if (firstInvalid !== null) {
        const el = inputs[firstInvalid] || form.querySelector('input[name="availability"]');
        if (el && typeof el.focus === 'function') el.focus();
        return;
      }

      // Validación correcta → simular envío y mostrar mensaje de éxito
      form.hidden = true;
      successBox.hidden = false;
      successBox.setAttribute('tabindex', '-1');
      successBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
      successBox.focus();
    });

    // ----- Limpiar formulario -----
    form.addEventListener('reset', function () {
      // El reset nativo borra los valores tras el evento; limpiamos UI en el siguiente tick
      setTimeout(function () {
        ORDER.forEach(function (name) { setFieldState(name, ''); });
        counter.textContent = 'Quedan ' + MAX_COMMENTS + ' caracteres';
        counter.classList.remove('text-red-600');
        counter.classList.add('text-slate-500');
        if (!successBox.hidden) successBox.hidden = true;
        if (form.hidden) form.hidden = false;
      }, 0);
    });
  });
})();
