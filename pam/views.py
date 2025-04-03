from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Employee, Workstation
from .forms import EmployeeForm, WorkstationForm

class EmployeeListView(ListView):
    model = Employee
    template_name = 'pam/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 10


class WorkstationCreateView(CreateView):
    model = Workstation
    form_class = WorkstationForm
    template_name = 'pam/workstation_form.html'
    success_url = reverse_lazy('pam:workstation_list')

    def get_initial(self):
        initial = super().get_initial()
        self.preselected_category = self.request.GET.get('category')
        if self.preselected_category:
            initial['category'] = self.preselected_category
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if hasattr(self, 'preselected_category') and self.preselected_category:
            kwargs['preselected_category'] = self.preselected_category
        return kwargs

class EmployeeCreateView(CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'pam/employee_form.html'
    success_url = reverse_lazy('pam:employee_list')

class EmployeeUpdateView(UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'pam/employee_form.html'
    success_url = reverse_lazy('pam:employee_list')

class EmployeeDeleteView(DeleteView):
    model = Employee
    template_name = 'pam/employee_confirm_delete.html'
    success_url = reverse_lazy('pam:employee_list')

class WorkstationListView(ListView):
    model = Workstation
    template_name = 'pam/workstation_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        categories = [
            {
                'name': 'Estágio',
                'original_value': 'ESTAGIO',
                'workstations': Workstation.objects.filter(category='ESTAGIO')
            },
            {
                'name': 'INSS',
                'original_value': 'INSS',
                'workstations': Workstation.objects.filter(category='INSS')
            },
            {
                'name': 'SIAPE Dion',
                'original_value': 'SIAPE_DION',
                'workstations': Workstation.objects.filter(category='SIAPE_DION')
            },
            {
                'name': 'SIAPE Leo',
                'original_value': 'SIAPE_LEO',
                'workstations': Workstation.objects.filter(category='SIAPE_LEO')
            }
        ]
        
        context['categories'] = categories
        return context

class WorkstationUpdateView(UpdateView):
    model = Workstation
    form_class = WorkstationForm
    template_name = 'pam/workstation_form.html'
    success_url = reverse_lazy('pam:workstation_list')

class WorkstationDeleteView(DeleteView):
    model = Workstation
    template_name = 'pam/workstation_confirm_delete.html'
    success_url = reverse_lazy('pam:workstation_list')

def home(request):
    return render(request, 'pam/home.html')
