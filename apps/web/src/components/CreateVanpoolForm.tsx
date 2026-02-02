'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Employee, Shift } from '@prisma/client';
import { createVanpool, type EmployeeInput } from '@/app/dev/create/actions';

interface CreateVanpoolFormProps {
  existingEmployees: Employee[];
  shifts: Shift[];
}

interface AddedEmployee {
  id: string; // temporary ID for list management
  type: 'existing' | 'new';
  employeeId?: string;
  firstName?: string;
  lastName?: string;
  email?: string;
  homeZip?: string;
  shiftId?: string;
  displayName: string;
  displayEmail: string;
  displayShift: string;
}

export function CreateVanpoolForm({ existingEmployees, shifts }: CreateVanpoolFormProps) {
  const router = useRouter();
  const [employees, setEmployees] = useState<AddedEmployee[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New employee form state
  const [showNewForm, setShowNewForm] = useState(false);
  const [newFirstName, setNewFirstName] = useState('');
  const [newLastName, setNewLastName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newHomeZip, setNewHomeZip] = useState('');
  const [newShiftId, setNewShiftId] = useState(shifts[0]?.id || '');

  // Existing employee dropdown
  const [selectedExistingId, setSelectedExistingId] = useState('');

  // Filter out already added employees from dropdown
  const availableEmployees = existingEmployees.filter(
    (emp) => !employees.some((e) => e.type === 'existing' && e.employeeId === emp.employeeId)
  );

  const getShiftName = (shiftId: string) => {
    const shift = shifts.find((s) => s.id === shiftId);
    return shift?.name || shiftId;
  };

  const handleAddExisting = () => {
    if (!selectedExistingId) return;

    const emp = existingEmployees.find((e) => e.employeeId === selectedExistingId);
    if (!emp) return;

    setEmployees([
      ...employees,
      {
        id: `existing-${emp.employeeId}`,
        type: 'existing',
        employeeId: emp.employeeId,
        displayName: `${emp.firstName} ${emp.lastName}`,
        displayEmail: emp.email,
        displayShift: getShiftName(emp.shiftId),
      },
    ]);
    setSelectedExistingId('');
  };

  const handleAddNew = () => {
    if (!newFirstName || !newLastName || !newEmail || !newHomeZip || !newShiftId) {
      setError('Please fill in all fields for the new employee');
      return;
    }

    // Check for duplicate email
    const emailExists =
      employees.some((e) => e.email === newEmail) ||
      existingEmployees.some((e) => e.email === newEmail);
    if (emailExists) {
      setError('An employee with this email already exists');
      return;
    }

    setEmployees([
      ...employees,
      {
        id: `new-${Date.now()}`,
        type: 'new',
        firstName: newFirstName,
        lastName: newLastName,
        email: newEmail,
        homeZip: newHomeZip,
        shiftId: newShiftId,
        displayName: `${newFirstName} ${newLastName}`,
        displayEmail: newEmail,
        displayShift: getShiftName(newShiftId),
      },
    ]);

    // Reset form
    setNewFirstName('');
    setNewLastName('');
    setNewEmail('');
    setNewHomeZip('');
    setNewShiftId(shifts[0]?.id || '');
    setShowNewForm(false);
    setError(null);
  };

  const handleRemove = (id: string) => {
    setEmployees(employees.filter((e) => e.id !== id));
  };

  const handleSubmit = async () => {
    if (employees.length === 0) {
      setError('Add at least one employee to create a vanpool');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    // Convert to EmployeeInput format
    const employeeInputs: EmployeeInput[] = employees.map((emp) => {
      if (emp.type === 'existing') {
        return { type: 'existing', employeeId: emp.employeeId };
      }
      return {
        type: 'new',
        firstName: emp.firstName,
        lastName: emp.lastName,
        email: emp.email,
        homeZip: emp.homeZip,
        shiftId: emp.shiftId,
      };
    });

    const result = await createVanpool(employeeInputs);

    if (result.success && result.vanpoolId) {
      router.push(`/vanpools/${result.vanpoolId}`);
    } else {
      setError(result.error || 'Failed to create vanpool');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Error message */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Add Employees Section */}
      <div className="border border-neutral-200 rounded-lg">
        <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
          <h2 className="text-sm font-medium text-neutral-900">Employees</h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            Add employees to this vanpool (existing or new)
          </p>
        </div>

        <div className="p-4 space-y-4">
          {/* Add existing employee */}
          <div className="flex gap-2">
            <select
              value={selectedExistingId}
              onChange={(e) => setSelectedExistingId(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
            >
              <option value="">Select existing employee...</option>
              {availableEmployees.map((emp) => (
                <option key={emp.employeeId} value={emp.employeeId}>
                  {emp.firstName} {emp.lastName} ({emp.email})
                </option>
              ))}
            </select>
            <button
              onClick={handleAddExisting}
              disabled={!selectedExistingId}
              className="px-4 py-2 text-sm font-medium bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Add
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-neutral-200" />
            <span className="text-xs text-neutral-400">or</span>
            <div className="flex-1 h-px bg-neutral-200" />
          </div>

          {/* New employee form toggle */}
          {!showNewForm ? (
            <button
              onClick={() => setShowNewForm(true)}
              className="w-full px-4 py-2 text-sm font-medium border border-dashed border-neutral-300 text-neutral-600 rounded-lg hover:border-neutral-400 hover:text-neutral-700 transition-colors"
            >
              + Create New Employee
            </button>
          ) : (
            <div className="border border-neutral-200 rounded-lg p-4 space-y-3 bg-neutral-50">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    value={newFirstName}
                    onChange={(e) => setNewFirstName(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                    placeholder="John"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">
                    Last Name
                  </label>
                  <input
                    type="text"
                    value={newLastName}
                    onChange={(e) => setNewLastName(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                    placeholder="Smith"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">Email</label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                  placeholder="john.smith@tesla.com"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Zip Code</label>
                  <input
                    type="text"
                    value={newHomeZip}
                    onChange={(e) => setNewHomeZip(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                    placeholder="94538"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">Shift</label>
                  <select
                    value={newShiftId}
                    onChange={(e) => setNewShiftId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                  >
                    {shifts.map((shift) => (
                      <option key={shift.id} value={shift.id}>
                        {shift.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleAddNew}
                  className="px-4 py-2 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 transition-colors"
                >
                  Add Employee
                </button>
                <button
                  onClick={() => {
                    setShowNewForm(false);
                    setError(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-800 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Added Employees List */}
      {employees.length > 0 && (
        <div className="border border-neutral-200 rounded-lg overflow-hidden">
          <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
            <h2 className="text-sm font-medium text-neutral-900">
              Added Employees ({employees.length})
            </h2>
          </div>
          <div className="divide-y divide-neutral-100">
            {employees.map((emp) => (
              <div
                key={emp.id}
                className="flex items-center justify-between px-4 py-3 hover:bg-neutral-50"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-neutral-100 text-xs font-medium text-neutral-600">
                    {emp.displayName
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-neutral-900">{emp.displayName}</span>
                      {emp.type === 'new' && (
                        <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">
                          new
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-neutral-500">{emp.displayEmail}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-neutral-500">{emp.displayShift}</span>
                  <button
                    onClick={() => handleRemove(emp.id)}
                    className="text-neutral-400 hover:text-red-600 transition-colors"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={employees.length === 0 || isSubmitting}
          className="px-6 py-2.5 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? 'Creating...' : 'Create Vanpool'}
        </button>
      </div>
    </div>
  );
}
